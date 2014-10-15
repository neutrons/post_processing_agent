#!/bin/bash
# Usage: startJob.sh <path to processing script> <destination> <data> 
module load mantid-mpi
module load sns_software
python $1 -q $2 -d $3
module unload mantid-mpi
module unload sns_software
