#!/usr/bin/env python
"""
    Cataloging process for raw data files.
    
    The original code for this class was take from https://github.com/mantidproject/autoreduce
    This code is a slightly cleaned up version of the original code.
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
VERSION = "1.4.2"

from suds.client import Client

import nxs, os, logging
import xml.utils.iso8601, ConfigParser
from xml.sax import saxutils

class IngestNexus():
    def __init__(self, infilename):
        self._infilename = infilename
        config = ConfigParser.RawConfigParser()
        config.read('/etc/autoreduce/icatclient.properties')
        hostAndPort = config.get('icat41', 'hostAndPort')
        password = config.get('icat41', 'password')
        plugin = "db"
        client = Client("https://" + hostAndPort + "/ICATService/ICAT?wsdl")
        self._service = client.service
        self._factory = client.factory
    
        credentials = self._factory.create("credentials")
        entry = self._factory.create("credentials.entry")
        entry.key = "username"
        entry.value = "root"
        credentials.entry.append(entry)
        entry = self._factory.create("credentials.entry")
        entry.key = "password"
        entry.value = password
        credentials.entry.append(entry)
    
        self._sessionId = self._service.login(plugin, credentials)
   
    def logout(self): 
        self._service.logout(self._sessionId)
    
    def execute(self):
        #find facility, investigation_type 
        config = ConfigParser.RawConfigParser()
        config.read('/etc/autoreduce/icat4.cfg')
        
        investigation = self._factory.create("investigation")
        
        #find facility, investigation_type 
        facility = self._factory.create("facility")
        facility.id = config.get('Facility', 'sns')
        investigation.facility = facility
            
        invType = self._factory.create("investigationType")
        invType.id = config.get('InvestigationType', 'experiment')
        investigation.type = invType 
    
        #open nexus file
        file = nxs.open(self._infilename, 'r')
        for name, nxclass in file.entries():
            if nxclass == "NXentry" and name != "entry-VETO":
                listing = file.getentries()
        
                #investigation name 
                if listing.has_key('experiment_identifier'):
                    file.opendata('experiment_identifier')
                    investigation.name = file.getdata()
                    file.closedata()
                else:
                    investigation.name = "IPTS-0000"
            
                #investigation title
                if listing.has_key('title'):
                    file.opendata('title')
                    investigation_title = unicode(file.getdata(), errors='replace')
                    investigation.title = investigation_title.encode('ascii', 'replace')
                    file.closedata()
                else:
                    investigation.title = "NONE"
            
                #create dataset
                dataset = self._factory.create("dataset")
                
                #investigation run number
                if listing.has_key('collection_identifier'):
                    file.opendata('collection_identifier')
                    investigation.visitId = str(file.getdata())
                    file.closedata()
                else:
                    investigation.visitId = "0"
            
                #dataset run number
                file.opendata('run_number')
                dataset.name = file.getdata() 
                file.closedata()
            
                #dataset title
                if listing.has_key('title'): 
                    file.opendata('title')
                    dataset_description = unicode(file.getdata(), errors='replace')
                    dataset.description = dataset_description.encode('ascii', 'replace')
                    file.closedata()
            
                dsType = self._factory.create("datasetType")
                dsType.id = config.get('DatasetType', 'experiment_raw')
                dataset.type = dsType
            
                #set dataset start time
                if listing.has_key('start_time'):
                    file.opendata('start_time')
                    dataset.startDate = file.getdata()
                    file.closedata()
        
                #set dataset end time
                if listing.has_key('end_time'): 
                    file.opendata('end_time')
                    dataset.endDate = file.getdata()
                    file.closedata()
            
                #dataset proton_charge 
                file.opendata('proton_charge')
                protonCharge = file.getdata()
                file.closedata()
            
                #dataset total_counts 
                file.opendata('total_counts')
                totalCounts = file.getdata()
                file.closedata()
            
                #dataset duration 
                file.opendata('duration')
                duration = file.getdata()
                file.closedata()
            
                #investigation instrument 
                file.opengroup('instrument')
                file.opendata('name')
                for attr,value in file.attrs():
                    if attr == 'short_name':
                        instrument = self._factory.create("instrument")
                        instrument.name = value 
                        instrument.id = config.get('Instrument', value.lower())
                        investigation.instrument = instrument 
                file.closedata()
                file.closegroup()
            
                #set dataset parameters
                parameters = []
            
                #1) parameter proton_charge 
                if protonCharge:
                    parameterType = self._factory.create("parameterType")
                    parameterType.id = config.get('ParameterType', 'proton_charge')
                    parameterType.applicableToDataset = config.getboolean('ParameterType', 'proton_charge_applicable_to_dataset')
                    datasetParameter = self._factory.create("datasetParameter")
                    datasetParameter.type = parameterType
                    datasetParameter.stringValue = protonCharge 
                    parameters.append(datasetParameter)
            
                #2) parameter total_counts 
                if totalCounts:
                    parameterType = self._factory.create("parameterType")
                    parameterType.id = config.get('ParameterType', 'total_counts')
                    parameterType.applicableToDataset = config.getboolean('ParameterType', 'total_counts_applicable_to_dataset')
                    datasetParameter = self._factory.create("datasetParameter")
                    datasetParameter.type = parameterType 
                    datasetParameter.numericValue = totalCounts
                    parameters.append(datasetParameter)
            
                #3) parameter duration 
                if duration:
                    parameterType = self._factory.create("parameterType")
                    parameterType.id = config.get('ParameterType', 'duration')
                    parameterType.applicableToDataset = config.getboolean('ParameterType', 'duration_applicable_to_dataset')
                    datasetParameter = self._factory.create("datasetParameter")
                    datasetParameter.type = parameterType 
                    datasetParameter.numericValue = duration 
                    parameters.append(datasetParameter)
                        
                dataset.parameters = parameters
                dataset.location = self._infilename 
            
                datafiles = []
            
                token=self._infilename.split("/")
                proposalDir = "/" + token[1] + "/" + token[2] + "/" + token[3]
                for dirpath, dirnames, filenames in os.walk(proposalDir):
                    if dirpath.find("shared") == -1 and dirpath.find("data") == -1:
                        for filename in [f for f in filenames]:
                            #if dataset.name in filename and os.path.islink(filename) != False:
                            if dataset.name in filename:
                                logging.info("Filename: %s" % filename)
                                datafile = self._factory.create("datafile")
                                filepath = os.path.join(dirpath,filename)
                                extension = os.path.splitext(filename)[1][1:]
                                datafile.name = filename
                                datafile.location = filepath
                                dfFormat = self._factory.create("datafileFormat")
                                dfFormat.id = config.get('DatafileFormat', extension)
                                datafile.datafileFormat = dfFormat 
                                modTime = os.path.getmtime(filepath)
                                datafile.datafileCreateTime = xml.utils.iso8601.tostring(modTime)
                                datafile.fileSize = os.path.getsize(filepath)
                                datafiles.append(datafile)
                
                dataset.datafiles = datafiles
                
                samples = []
                
                sample = self._factory.create("sample")
                sample.name = 'NONE'
                
                if listing.has_key('sample'):
                    file.opengroup('sample')
                    listSample = file.getentries()
                    if listSample.has_key('name'):
                        file.opendata('name')
                        # Text stored in the Nexus file is XML escaped
                        # ICAT unescapes it automatically, so we need to
                        # do it here if we want to determine whether
                        # the sample is already in the DB.
                        sample_name = unicode(file.getdata(), errors='replace')
                        sample.name = saxutils.unescape(sample_name.encode('ascii', 'replace'))
                        file.closedata()
                    else:
                        sample.name = "NONE"
                    sampleParameters = []
                
                    #set sample nature
                    if listSample.has_key('nature'):
                        file.opendata('nature')
                        nature = file.getdata()
                        file.closedata()
                        if nature:
                            parameterType = self._factory.create("parameterType")
                            parameterType.id = config.get('ParameterType', 'nature')
                            parameterType.applicableToSample = config.getboolean('ParameterType', 'nature_applicable_to_sample')
                            sampleParameter = self._factory.create("sampleParameter")
                            sampleParameter.type = parameterType
                            sampleParameter.stringValue = nature 
                            sampleParameters.append(sampleParameter)
                        
                    if listSample.has_key('identifier'):
                        file.opendata('identifier')
                        identifier = file.getdata()
                        file.closedata()
                  
                        if identifier:
                            parameterType = self._factory.create("parameterType")
                            parameterType.id = config.get('ParameterType', 'identifier')
                            parameterType.applicableToSample = config.getboolean('ParameterType', 'identifier_applicable_to_sample')
                            sampleParameter = self._factory.create("sampleParameter")
                            sampleParameter.type = parameterType
                            sampleParameter.stringValue = identifier
                            sampleParameters.append(sampleParameter)
                       
                    if len(sampleParameters): 
                        sample.parameters = sampleParameters
                
                    file.closegroup()
                samples.append(sample)
                break 
        
        file.close()
        
        dbDatasets = self._service.search(self._sessionId, "Dataset INCLUDE Datafile [name = '" + str(dataset.name) + "'] <-> Investigation <-> Instrument [name = '" + str(instrument.name) + "'] <-> DatasetType [name = 'experiment_raw']")

        if len(dbDatasets) == 0:
            dbInvestigations = self._service.search(self._sessionId, "Investigation INCLUDE Sample [name = '" + investigation.name + "' AND visitId = '" + investigation.visitId + "'] <-> Instrument [name = '" + instrument.name + "']")
        
            if len(dbInvestigations) == 0: 
                logging.debug("New IPTS: creating investigation, sample, run...")
                # create new investigation
                invId = self._service.create(self._sessionId, investigation)
                investigation.id = invId
            
                # create new sample
                sample.investigation = investigation
                sampleId = self._service.create(self._sessionId, sample)
                sample.id = sampleId
                logging.debug("  invId: %s  sampleId: %s" % (str(invId), str(sampleId)))
        
            elif len(dbInvestigations) == 1:
                investigation = dbInvestigations[0]
                dbSamples = investigation.samples
            
                newSample = True
                for dbSample in dbSamples:
                    if dbSample.name == sample.name:
                        sample.id = dbSample.id
                        newSample = False
            
                if newSample == True:
                    logging.debug("New run: existing investigation, creating sample and run...")
                    sample.investigation = investigation
                    sampleId = self._service.create(self._sessionId, sample)
                    sample.id = sampleId
                else:
                    logging.debug("New run: existing investigation and sample, creating run...")
            
            else:
                logging.error("ERROR, there should be only one investigation per instrument per investigation name")

            # create new dataset
            dataset.sample = sample
            dataset.investigation = investigation
            datasetId = self._service.create(self._sessionId, dataset)
            logging.debug("  datasetId: %s" % str(datasetId))
            
        elif len(dbDatasets) == 1:
            logging.debug("Run %s is already cataloged, updating catalog..." % dataset.name)
        
            dbDataset = dbDatasets[0]
            logging.debug("  datasetId: %s" % str(dbDataset.id))
        
            # update "one to many" relationships
        
            if hasattr(dbDataset, "datafiles"):
                dfs = getattr(dbDataset, "datafiles")
                self._service.deleteMany(self._sessionId, dfs)
            
            for df in datafiles:
                df.dataset = dbDataset
            self._service.createMany(self._sessionId, datafiles)
        
            # update "many to one" relationships
        
            ds = self._service.get(self._sessionId, "Dataset INCLUDE 1", dbDataset.id)   
            investigation.id = ds.investigation.id
        
            dbSamples = self._service.search(self._sessionId, "Sample <-> Investigation [id = '" + str(ds.investigation.id) + "']")
            updateSample = True
            for sa in dbSamples:
                if sa.name == sample.name:
                    sample = sa
                    updateSample = False
             
            if updateSample == True:
                sample.id = ds.sample.id
                sample.investigation = investigation
                self._service.update(self._sessionId, sample)
        
            dataset.id = ds.id
            dataset.sample = sample
            dataset.investigation = investigation   
        
            self._service.update(self._sessionId, dataset)
            self._service.update(self._sessionId, investigation)
       
        else:
            logging.error("ERROR, there should be only one dataset per run number per type experiment_raw")
