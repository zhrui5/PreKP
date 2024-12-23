from typing import List, Union, Tuple
import numpy as np
from rdkit import Chem
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence

from .ple import PLE

from collections import OrderedDict
import ipdb

import torch
import torch.nn as nn

import ipdb
import torch
from torch import nn
from torch import einsum


class MoleculeModel(nn.Module):
    """A :class:`MoleculeModel` is a model which contains a message passing network following by feed-forward layers."""


    def create_ffn(self, args: prekp_args) -> None:
        """
        Creates the feed-forward layers for the model.

        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        second_linear_dim = None
        self.multiclass = args.dataset_type == "multiclass"
        if self.multiclass:
            self.num_classes = args.multiclass_num_classes
        if args.features_only:
            first_linear_dim = args.features_size
        else:
            if args.reaction_solvent and not args.reaction_substrate:
                first_linear_dim = args.hidden_size + args.hidden_size_solvent
            elif args.reaction_solvent and args.reaction_substrate:
                first_linear_dim = args.hidden_size
                second_linear_dim = args.hidden_size_solvent
            else:
                first_linear_dim = args.hidden_size * args.number_of_molecules
            if args.use_input_features:
                first_linear_dim += args.features_size

        if args.atom_descriptors == "descriptor":
            atom_first_linear_dim = first_linear_dim + args.atom_descriptors_size
        else:
            atom_first_linear_dim = first_linear_dim

        if args.bond_descriptors == "descriptor":
            bond_first_linear_dim = first_linear_dim + args.bond_descriptors_size
        else:
            bond_first_linear_dim = first_linear_dim


        if self.is_atom_bond_targets:
            self.readout = MultiReadout(
                atom_features_size=atom_first_linear_dim,
                bond_features_size=bond_first_linear_dim,
                atom_hidden_size=args.ffn_hidden_size + args.atom_descriptors_size,
                bond_hidden_size=args.ffn_hidden_size + args.bond_descriptors_size,
                num_layers=args.ffn_num_layers,
                output_size=self.relative_output_size,
                dropout=args.dropout,
                activation=args.activation,
                atom_constraints=args.atom_constraints,
                bond_constraints=args.bond_constraints,
                shared_ffn=args.shared_atom_bond_ffn,
                weights_ffn_num_layers=args.weights_ffn_num_layers,
            )
        else:
            first_linear_dim_now = atom_first_linear_dim
            if not args.skip_protein and not args.protein_records_path is None:
                first_linear_dim_now += args.seq_embed_dim
                if args.add_esm_feats:
                    first_linear_dim_now += 1280
            
            elif args.skip_protein and args.include_embed_features:
                first_linear_dim_now += args.embed_mlp_output_size

            # create PLE mode
            self.readout = PLE(
                experts_in=first_linear_dim_now, 
                experts_out=self.relative_output_size, 
                experts_hidden=args.experts_hidden_size, 
                expert_hid_layer=args.expert_hid_layer,  
                dropout_rate=args.dropout_rate,  
                num_experts=args.num_experts,  
                num_tasks=args.num_tasks_ple, 
                num_ple_layers=args.num_ple_layers,  
            )
            

        if args.checkpoint_frzn is not None:
            if args.frzn_ffn_layers > 0:
                if self.is_atom_bond_targets:
                    if args.shared_atom_bond_ffn:
                        for param in list(self.readout.atom_ffn_base.parameters())[
                            0 : 2 * args.frzn_ffn_layers
                        ]:
                            param.requires_grad = False
                        for param in list(self.readout.bond_ffn_base.parameters())[
                            0 : 2 * args.frzn_ffn_layers
                        ]:
                            param.requires_grad = False
                    else:
                        for ffn in self.readout.ffn_list:
                            if ffn.constraint:
                                for param in list(ffn.ffn.parameters())[
                                    0 : 2 * args.frzn_ffn_layers
                                ]:
                                    param.requires_grad = False
                            else:
                                for param in list(ffn.ffn_readout.parameters())[
                                    0 : 2 * args.frzn_ffn_layers
                                ]:
                                    param.requires_grad = False
                else:
                    for param in list(self.readout.parameters())[
                        0 : 2 * args.frzn_ffn_layers
                    ]:  # Freeze weights and bias for given number of layers
                        param.requires_grad = False


    def __init__(self, args: prekp_args):
        """
        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        super(MoleculeModel, self).__init__()
        self.classification = args.dataset_type == "classification"
        self.multiclass = args.dataset_type == "multiclass"
        self.loss_function = args.loss_function
        self.args = args
        self.device = args.device

        if hasattr(args, "train_class_sizes"):
            self.train_class_sizes = args.train_class_sizes
        else:
            self.train_class_sizes = None


        if self.classification or self.multiclass:
            self.no_training_normalization = args.loss_function in [
                "cross_entropy",
                "binary_cross_entropy",
            ]

        self.is_atom_bond_targets = args.is_atom_bond_targets

        if self.is_atom_bond_targets:
            self.atom_targets, self.bond_targets = args.atom_targets, args.bond_targets
            self.atom_constraints, self.bond_constraints = (
                args.atom_constraints,
                args.bond_constraints,
            )
            self.adding_bond_types = args.adding_bond_types

        self.relative_output_size = 1
        if self.multiclass:
            self.relative_output_size *= args.multiclass_num_classes
        if self.loss_function == "mve":
            self.relative_output_size *= 2  # return means and variances
        if self.loss_function == "dirichlet" and self.classification:
            self.relative_output_size *= (
                2  # return dirichlet parameters for positive and negative class
            )
        if self.loss_function == "evidential":
            self.relative_output_size *= (
                4  
            )

        if self.classification:
            self.sigmoid = nn.Sigmoid()

        if self.multiclass:
            self.multiclass_softmax = nn.Softmax(dim=2)

        if self.loss_function in ["mve", "evidential", "dirichlet"]:
            self.softplus = nn.Softplus()

        self.create_encoder(args)
        
        if args.include_embed_features: self.create_embed_model(args)
        
        print('Creating protein model')
        self.create_protein_model(args)
        self.create_ffn(args)

        initialize_weights(self)
   

    def create_embed_model(self, args: prekp_args) -> None:
        """
        Creates the embedding model.
        :param args: A :class:`~prekp.args.prekp` object containing model arguments.
        """
        self.embed_model = EmbedderModel(args)
        
    def create_sequence_model(self, args: prekp_args) -> None:
        """
        Creates the sequence model.

        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        self.sequence_model = build_ffn(
                            first_linear_dim = args.gvp_node_hidden_dims[0] * args.gvp_num_layers,
                            hidden_size = args.protein_mlp_hidden_size,
                            num_layers = args.protein_mlp_num_layers,
                            output_size = args.protein_mlp_output_size,
                            dropout = args.protein_mlp_dropout,
                            activation = args.activation)
    
    def create_protein_model(self, args: prekp_args) -> None:
        """
        Creates protein model

        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """

        self.seq_embedder = nn.Embedding(21, args.seq_embed_dim, padding_idx=20) #last index is for padding

        if args.use_transformer:
            self.transformer = TransformerEncoder(vocab_size = 21, 
                                                      qty_encoder_layer = 3,
                                                      qty_attention_head = 6,
                                                      dim_vocab_embedding = args.seq_embed_dim,
                                                      dim_model = args.seq_embed_dim,
                                                      dim_inner_hidden = args.seq_embed_dim,
                                                      embedding = False).to(self.device)
        elif args.use_resnet:
            resnet_config = ProteinResNetConfig(hidden_size=args.seq_embed_dim)
            self.resnet = ResNet(resnet_config).to(self.device)
            
        elif self.args.use_egnn:
            depth = 3
            self.egnn_net = EGNN_Net(self.args.seq_embed_dim, self.device, valid_radius = 15)
            

        self.rotary_embedder = RotaryEmbedding(dim=args.seq_embed_dim//4)
        

        self.multihead_attn = nn.MultiheadAttention(args.seq_embed_dim, 
                                                    args.seq_self_attn_nheads, 
                                                    batch_first=True)

        seq_attn_pooling_dim = args.seq_embed_dim

        if args.add_esm_feats:
            seq_attn_pooling_dim+=1280
            
        self.attentive_pooler = AttentivePooling(seq_attn_pooling_dim, seq_attn_pooling_dim)
        self.max_pooler = lambda x: torch.max(x, dim=1, 
                                              keepdim=False, out=None)
        
        
    def create_encoder(self, args: prekp_args) -> None:
        """
        Creates the message passing encoder for the model.

        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        self.encoder = MPN(args)

        if args.checkpoint_frzn is not None:
            if args.freeze_first_only:  # Freeze only the first encoder
                for param in list(self.encoder.encoder.children())[0].parameters():
                    param.requires_grad = False
            else:  # Freeze all encoders
                for param in self.encoder.parameters():
                    param.requires_grad = False
                    
    def create_embed_model(self, args: prekp_args) -> None:
        """
        Creates the embedding model.

        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        self.embed_model = EmbedderModel(args)

    def fingerprint(
        self,
        batch: Union[
            List[List[str]],
            List[List[Chem.Mol]],
            List[List[Tuple[Chem.Mol, Chem.Mol]]],
            List[BatchMolGraph],
        ],
        features_batch: List[np.ndarray] = None,
        atom_descriptors_batch: List[np.ndarray] = None,
        atom_features_batch: List[np.ndarray] = None,
        bond_descriptors_batch: List[np.ndarray] = None,
        bond_features_batch: List[np.ndarray] = None,
        fingerprint_type: str = "MPN",
    ) -> torch.Tensor:

        if fingerprint_type == "MPN":
            return self.encoder(
                batch,
                features_batch,
                atom_descriptors_batch,
                atom_features_batch,
                bond_descriptors_batch,
                bond_features_batch,
            )
        elif fingerprint_type == "embed":
            return self.embed_model(
                batch,
                features_batch,
                atom_descriptors_batch,
                atom_features_batch,
                bond_descriptors_batch,
                bond_features_batch,
            )
        elif fingerprint_type == "last_FFN":
            return self.readout[1](
                self.readout(
                    batch,
                    features_batch,
                    atom_descriptors_batch,
                    atom_features_batch,
                    bond_descriptors_batch,
                    bond_features_batch,
                )
            )
        else:
            raise ValueError(f"Unsupported fingerprint type {fingerprint_type}.")

    def forward(
        self,
        batch: Union[
            List[List[str]],
            List[List[Chem.Mol]],
            List[List[Tuple[Chem.Mol, Chem.Mol]]],
            List[BatchMolGraph],
        ],
        features_batch: List[np.ndarray] = None,
        atom_descriptors_batch: List[np.ndarray] = None,
        atom_features_batch: List[np.ndarray] = None,
        bond_descriptors_batch: List[np.ndarray] = None,
        bond_features_batch: List[np.ndarray] = None,
        constraints_batch: List[torch.Tensor] = None,
        bond_types_batch: List[torch.Tensor] = None,
        return_fp: bool = False
    ) -> torch.Tensor:

        def seq_to_tensor(seq):
            letter_to_num = {'C': 4, 'D': 3, 'S': 15, 'Q': 5, 'K': 11, 'I': 9,
                       'P': 14, 'T': 16, 'F': 13, 'A': 0, 'G': 7, 'H': 8,
                       'E': 6, 'L': 10, 'R': 1, 'W': 17, 'V': 19, 
                       'N': 2, 'Y': 18, 'M': 12} 
            seq = torch.as_tensor([letter_to_num[a] for a in seq],
                                  device=self.device, dtype=torch.long)
            return seq
        
        if self.is_atom_bond_targets:
            encodings = self.encoder(
                batch,
                features_batch,
                atom_descriptors_batch,
                atom_features_batch,
                bond_descriptors_batch,
                bond_features_batch,
            )
            output = self.readout(encodings, constraints_batch, bond_types_batch)
        else:
            encodings = self.encoder(
                batch,
                features_batch,
                atom_descriptors_batch,
                atom_features_batch,
                bond_descriptors_batch,
                bond_features_batch,
            )

            if self.args.include_embed_features:
                embed_feature_arr = torch.from_numpy(np.array(batch[-1].embed_feature_list)).to(torch.int64).to(self.device) + 1
                try:
           
                    embed_output = self.embed_model(embed_feature_arr)
                except:
                    print('Something wrong in embed model')
                encodings = torch.concat([encodings,embed_output],dim=-1)
                
            if not self.args.skip_protein and not self.args.protein_records_path is None:
                protein_records = batch[-1].protein_record_list
                
                seq_arr = [seq_to_tensor(each['seq']) for each in protein_records]
                seq_arr = pad_sequence(seq_arr, batch_first=True,
                                       padding_value=20).to(self.device)

                if self.args.add_esm_feats:
                    esm_feature_arr = [each['esm2_feats'] for each in protein_records]
                    esm_feature_arr = pad_sequence(esm_feature_arr,
                                                   batch_first=True).to(self.device)
                    if seq_arr.shape[1]!=esm_feature_arr.shape[1]: 
                        seq_arr = seq_arr[:,:esm_feature_arr.shape[1]:]


                seq_outs = self.seq_embedder(seq_arr)
                
                if self.args.use_transformer:
                    seq_outs = self.transformer(seq_outs)
                    if self.add_esm_feats:
                        seq_outs = torch.cat([esm_feature_arr, seq_outs], dim=-1)
                    seq_pooled_outs, seq_wts = self.attentive_pooler(seq_outs)
                    
                elif self.args.use_resnet:
                    seq_outs = self.resnet(seq_outs.transpose(1,2))[0]
                    seq_outs = seq_outs.transpose(1,2)
                    seq_pooled_outs = self.max_pooler(seq_outs).values
                    if self.args.add_esm_feats:
                        seq_pooled_outs = torch.cat([esm_feature_arr.mean(dim=1), 
                                                     seq_pooled_outs], dim=-1)
                
                elif self.args.use_egnn:
             
                    coord_arr = [torch.as_tensor(each['coords'], 
                                                 device='cuda', 
                                                 dtype=torch.float32) for each in protein_records]
                    
                    coords = pad_sequence(coord_arr,batch_first=True,
                                           padding_value=0).to(self.device)[:,:,1,:]
                    mask = torch.isfinite(coords.sum(dim=(-1)))
                    coords[~mask] = 0

                    if seq_arr.shape[1]!=coords.shape[1]: 
                        coords = coords[:,:seq_arr.shape[1],:]
                        mask = mask[:,:seq_arr.shape[1]]

                    seq_outs = self.rotary_embedder.rotate_queries_or_keys(seq_outs,
                                                                 seq_dim=1)
                    seq_outs = self.egnn_net(seq_outs, coords)
                    if self.args.add_esm_feats:
                        seq_outs = torch.cat([esm_feature_arr, seq_outs], dim=-1)
                    
               
                    if not self.args.skip_attentive_pooling:
                        seq_pooled_outs, seq_wts = self.attentive_pooler(seq_outs)
                    else:
                        seq_pooled_outs = seq_outs.mean(dim=1)
                else:

                    q = self.rotary_embedder.rotate_queries_or_keys(seq_outs,
                                                                 seq_dim=1)
                    k = self.rotary_embedder.rotate_queries_or_keys(seq_outs,
                                                                seq_dim=1)    

                    seq_outs, _ = self.multihead_attn(q, k, seq_outs)

                    if self.args.add_esm_feats:
                        if esm_feature_arr.shape[1] != seq_outs.shape[1]:
                            required_padding = abs(esm_feature_arr.shape[1] - seq_outs.shape[1])
                            if esm_feature_arr.shape[1] < seq_outs.shape[1]:
                                esm_feature_arr = torch.nn.functional.pad(esm_feature_arr, (0, 0, 0, required_padding))
                            else:
                                seq_outs = torch.nn.functional.pad(seq_outs, (0, 0, 0, required_padding))
                           
                     
                        seq_outs = torch.cat([esm_feature_arr, seq_outs], dim=-1)
                        
       
                    if not self.args.skip_attentive_pooling:
                        seq_pooled_outs, seq_wts = self.attentive_pooler(seq_outs)
                    else:
                        seq_pooled_outs = seq_outs.mean(dim=1)
                
                total_outs = torch.cat([seq_pooled_outs, encodings], dim=-1)
                if return_fp: fp = self.readout[1](total_outs)

                outputs = self.readout(total_outs)

                output = torch.cat(outputs, dim=1)
            else:
                outputs = self.readout(encodings)
                if return_fp: fp = self.readout[1](encodings)
                output = torch.cat(outputs, dim=1)


        if (
            self.classification
            and not (self.training and self.no_training_normalization)
            and self.loss_function != "dirichlet"
        ):
            output = self.sigmoid(output)
        if self.multiclass:
            output = output.reshape(
                (output.shape[0], -1, self.num_classes)
            )  # batch size x num targets x num classes per target
            if (
                not (self.training and self.no_training_normalization)
                and self.loss_function != "dirichlet"
            ):
                output = self.multiclass_softmax(
                    output
                )  # to get probabilities during evaluation, but not during training when using CrossEntropyLoss


        if self.loss_function == "mve":
            means, variances = torch.split(output, output.shape[1] // 2, dim=1)
            variances = self.softplus(variances)
            output = torch.cat([means, variances], axis=1)
        if self.loss_function == "evidential":
            means, lambdas, alphas, betas = torch.split(
                output, output.shape[1] // 4, dim=1
            )
            lambdas = self.softplus(lambdas)  # + min_val
            alphas = (
                self.softplus(alphas) + 1
            )  # + min_val # add 1 for numerical constraints of Gamma function
            betas = self.softplus(betas)  # + min_val
            output = torch.cat([means, lambdas, alphas, betas], dim=1)
        if self.loss_function == "dirichlet":
            output = nn.functional.softplus(output) + 1

        if return_fp:
            return output, fp
        else:
            return output
  
def exists(val):
    return val is not None

def default(val, d):
    return val if exists(val) else d
    
class EmbedderModel(nn.Module):


    def __init__(self, args: prekp_args):
        """
        :param args: A :class:`~prekp.args.prekp_args` object containing model arguments.
        """
        super(EmbedderModel, self).__init__()

        self.embed_dim_fn = lambda x: int(np.power(x, args.embed_size_to_dim_power))+1
        self.device = args.device

        self.embed_layers = []
        embed_dims = []
        for size in args.embed_sizes:
            dim = self.embed_dim_fn(size)
            embed_dims.append(dim)
            layer = nn.Embedding(size, dim).to(self.device)

            nn.init.kaiming_normal_(layer.weight, nonlinearity='leaky_relu')
            self.embed_layers.append(layer)

        self.embed_dropout = nn.Dropout(args.embed_dropout) if args.embed_dropout>0 else None

        self.mlp_module = build_ffn(
                first_linear_dim = sum(embed_dims),
                hidden_size = args.embed_mlp_hidden_size,
                num_layers = args.embed_mlp_num_layers,
                output_size = args.embed_mlp_output_size,
                dropout = args.embed_mlp_dropout,
                activation = 'LeakyReLU'
                )

    def forward(self, categorical_data: torch.Tensor) -> torch.Tensor:

        embeds = []
        for i, embedding_layer in enumerate(self.embed_layers):
      
            embeds.append(embedding_layer(categorical_data[:,i]))
        embeds = torch.cat(embeds, dim=1)

        if self.embed_dropout is not None:
            embeds = self.embed_dropout(embeds)

        output = self.mlp_module(embeds)

        return output
    
class EGNN_Net(nn.Module):
    def __init__(self, dim, device, depth = 3, edge_dim = 0,
                                m_dim = 16,
                                fourier_features = 0,
                                num_nearest_neighbors = 30,
                                dropout = 0.0,
                                init_eps = 1e-3,
                                norm_feats = True,
                                norm_coors = True,
                                norm_coors_scale_init = 1e-2,
                                update_feats = True,
                                update_coors = False,
                                only_sparse_neighbors = False,
                                valid_radius = float('inf'),
                                m_pool_method = 'sum',
                                soft_edges = True,
                                coor_weights_clamp_value = 2.):
        super(EGNN_Net, self).__init__()
        self.depth = depth
        self.layers = [EGNN(dim, edge_dim,
                                m_dim,
                                fourier_features,
                                num_nearest_neighbors,
                                dropout,
                                init_eps,
                                norm_feats,
                                norm_coors,
                                norm_coors_scale_init,
                                update_feats,
                                update_coors,
                                only_sparse_neighbors,
                                valid_radius,
                                m_pool_method,
                                soft_edges,
                                coor_weights_clamp_value).to(device) for _ in range(depth)]

    def forward(self, feats, coords):
        for layer in self.layers:
            feats, coords = layer(feats, coords)
            
        return feats
    
class AttentivePooling(nn.Module):
    def __init__(self, input_size=1280, hidden_size=1280):
        super(AttentivePooling, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Attention mechanism components
        self.linear1 = nn.Linear(input_size, hidden_size)
        self.tanh = nn.Tanh()
        self.linear2 = nn.Linear(hidden_size, 1)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, input_tensor):
        # Calculate attention weights
        attn_scores = self.linear2(self.tanh(self.linear1(input_tensor)))
        attn_weights = self.softmax(attn_scores)

        # Apply attention weights to the input tensor
        attn_applied = torch.bmm(attn_weights.permute(0, 2, 1), input_tensor)

        return attn_applied.squeeze(1), attn_weights.squeeze(-1)
    


      


