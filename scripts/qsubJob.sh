#!/bin/bash
#PBS -l walltime=2:00:00
#PBS -N AUTO_REDUCTION
#PBS -V
#PBS -W umask=022

# module load mantid-mpi
export OMP_NUM_THREADS=16

reduce_script="/"$facility"/"$instrument"/shared/autoreduce/reduce_"$instrument".py"

python $reduce_script $data_file $proposal_shared_dir
