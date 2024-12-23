#!/bin/bash
#SBATCH --job-name=train_prekp
#SBATCH --partition=4090
#SBATCH --nodes=1                     
#SBATCH --ntasks-per-node=1            
#SBATCH --gres=gpu:2                
#SBATCH --output=out_sh/%j_%x.out 
#SBATCH --mem=120G  

source /public/home/anaconda3/etc/profile.d/conda.sh
conda activate prekp

python train.py --dataset_type regression

