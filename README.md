# PreKP
## Model framework
![截屏2024-12-23 14 26 46](https://github.com/user-attachments/assets/04905021-0977-4251-8237-969f34cad6df)

## Unbiased dataset distribution

![截屏2024-12-23 14 07 07](https://github.com/user-attachments/assets/5632aa5f-0f5e-48a5-8f1d-17e011dbbd8b)


# Description
This repository contains the code about the framework of our model presented by our paper "Enhancing Enzyme Kinetics Parameter Predictions with PreKP: A Deep Learning-Based Model"
# Introduction of PreKP
The rate of reaction and the activity of enzyme
catalysis are measured by enzymatic kinetic parameters,
specifically the turnover number kcat and the Michaelis
constant (Km). Precise prediction of these parameters is
essential for enzyme engineering for enzyme discovery
and optimization. Experimentally determining kcat and Km
requires significant time, effort, and expense, while existing
machine learning and deep learning approaches for pre-
dicting enzyme kinetic parameters often suffer from insuf-
ficient accuracy or limited generalization due to overfitting.
In response to these issues, we used fair and unbiased
datasets to assess the true performance of the models.
Moreover, to further enhance the precision and generaliza-
tion of our deep learning model, PreKP, we considered the
intrinsic relationships between kcat , Km, and the inhibition
constant related to the substrate or product binding kinetic
parameters (Ki) in training data to improve the predictive
performance of PreKP
# Background
##  Prerequisites
+ OS support: Linux(Ubantu)
## Create the PreKP environment
```plaintext
Name                    Version                   Build  Channel
python                    3.12.3          hab00c5b_0_cpython    conda-forge
pip                       23.3.1          py312h06a4308_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
pytorch                   2.2.0           py3.12_cuda11.8_cudnn8.7.0_0    pytorch
matplotlib                3.8.0           py312h06a4308_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
numpy                     1.26.4          py312hc5e2394_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
pandas-flavor             0.6.0              pyhd8ed1ab_1    conda-forge
pandas                    2.2.1           py312h526ad5a_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
rdkit                     2024.03.1       py312h93d94ad_0    conda-forge
threadpoolctl             2.2.0              pyh0d69192_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
scikit-learn              1.3.0           py312h526ad5a_2    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
scipy                     1.13.0          py312heda63a1_0    conda-forge
tensorboardx              2.2                pyhd3eb1b0_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
torchvision               0.17.0              py312_cu118    pytorch
tqdm                      4.65.0          py312he106c6f_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
transformers              4.17.0             pyhd8ed1ab_0    conda-forge
biopython                 1.83
biotite                   0.40.0
fair-esm                  2.0.0
matplotlib                3.8.0
rotary-embedding-torch    0.5.3
torch-cluster             1.6.3+pt22cu118          pypi_0    pypi
torch-geometric           2.5.3                    pypi_0    pypi
torch-scatter             2.1.2+pt22cu118          pypi_0    pypi
torch-sparse              0.6.18+pt22cu118          pypi_0    pypi
torch-spline-conv         1.2.2+pt22cu118          pypi_0    pypi
torchaudio                2.2.0               py312_cu118    pytorch
fair-esm                  2.0.0                    pypi_0    pypi
ffmpeg                    4.3                  hf484d3e_0    pytorch
filelock                  3.13.4             pyhd8ed1ab_0    conda-forge
pytorch-mutex             1.0                        cuda    pytorch
pytz                      2023.3.post1    py312h06a4308_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
pyyaml                    6.0.1           py312h98912ed_1    conda-forge
pyzmq                     26.0.0          py312h886d080_0    conda-forge
matplotlib-base           3.8.0           py312h526ad5a_0    https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
matplotlib-inline         0.1.7              pyhd8ed1ab_0    conda-forge
typed-argument-parser     1.10.0
typing_extensions         4.9.0

```
# Usage
## create conda environment 
```plaintext
pip install torch
pip install numpy
pip insatll matplotlib
pip install pandas= 1.3.0
```

## Submit jobs using slurm
```plaintext
#!/bin/bash
#SBATCH --job-name=***
#SBATCH --partition=A100
#SBATCH --nodes=1                     
#SBATCH --ntasks-per-node=1            
#SBATCH --gres=gpu:2                
#SBATCH --output=*** 
#SBATCH --mem=***（120G）  

source /public/home/anaconda/etc/profile.d/conda.sh
conda activate prekp

python ***（your file） --dataset_type regression
```

# Question and Answer
- The detailed training process will come soon.




