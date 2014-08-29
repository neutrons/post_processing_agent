#!/bin/bash
#PBS -l walltime=2:00:00
#PBS -N AUTO_REDUCTION
#PBS -V
#PBS -W umask=022

module load mantid-mpi
module load sns_software
export OMP_NUM_THREADS=16

mpirun -n $n_nodes python $reduce_script $data_file $proposal_shared_dir
