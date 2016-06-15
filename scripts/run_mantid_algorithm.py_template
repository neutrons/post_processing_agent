import mantid
from mantid.simpleapi import *

# Algorithm properties
properties = ${algorithm_properties}

# Create the algorithm and get its properties
alg = mantid.api.AlgorithmManager.createUnmanaged("${algorithm}")
alg.initialize()
property_list = alg.orderedProperties()

# Fill in the properties with the information we have
for key, value in properties.iteritems():
    if key in property_list:
        alg.setPropertyValue(str(key), str(value))
        
alg.execute()

