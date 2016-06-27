#!/usr/bin/env python
"""
    Cataloging process for reduced data files.

    The original code for this class was take from https://github.com/mantidproject/autoreduce
    This code is a slightly cleaned up version of the original code.

    @copyright: 2014 Oak Ridge National Laboratory
"""
VERSION = "1.4.2"

from suds.client import Client

import os, glob, logging
import ConfigParser
from time_conversions import epochToISO8601
from datetime import datetime

class IngestReduced():
    def __init__(self, facilityName, instrumentName, investigationName, runNumber):
        self._facilityName = facilityName
        self._instrumentName = instrumentName
        self._investigationName = investigationName
        self._runNumber = runNumber
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

        logging.debug("Begin login at: %s" % datetime.now())
        self._sessionId = self._service.login(plugin, credentials)
        logging.debug("End login at: %s" % datetime.now())

    def logout(self):
        logging.debug("Begin logout at: %s" % datetime.now())
        self._service.logout(self._sessionId)
        logging.debug("End logout at: %s" % datetime.now())

    def execute(self):
        """
            Catalog reduced data files
        """
        config = ConfigParser.RawConfigParser()
        config.read('/etc/autoreduce/icat4.cfg')

        directory = "/" + self._facilityName + "/" + self._instrumentName + "/" +  self._investigationName + "/shared/autoreduce"
        logging.info("reduction output directory: %s" % directory)

        #set dataset name
        dataset = self._factory.create("dataset")

        dsType = self._factory.create("datasetType")
        dsType.id = config.get('DatasetType', 'reduced')
        dataset.type = dsType
        dataset.name = self._runNumber
        dataset.location = directory
        datafiles = []

        pattern =  '*' + self._runNumber + '*'
        for dirpath, dirnames, filenames in os.walk(directory):
            listing = glob.glob(os.path.join(dirpath, pattern))
            for filepath in listing:
                filename =os.path.basename(filepath)
                logging.info("Filename: %s" % filename)
                datafile = self._factory.create("datafile")
                datafile.location = filepath
                datafile.name = filename
                extension = os.path.splitext(filename)[1][1:]
                dfFormat = self._factory.create("datafileFormat")
                dfFormat.id = config.get('DatafileFormat', extension)
                datafile.datafileFormat = dfFormat
                modTime = os.path.getmtime(filepath)
                datafile.datafileCreateTime = epochToISO8601(modTime)
                datafile.fileSize = os.path.getsize(filepath)

                datafiles.append(datafile)

        dataset.datafiles = datafiles
        dataset.type = dsType

        dbDatasets = self._service.search(self._sessionId, "Dataset INCLUDE Datafile [name = '" + str(dataset.name) + "'] <-> Investigation <-> Instrument [name = '" + str(self._instrumentName) + "'] <-> DatasetType [name = 'reduced']")

        if len(dbDatasets) == 0:

            dbInvestigations = self._service.search(self._sessionId, "Investigation INCLUDE Sample [name = '" + str(self._investigationName) + "'] <-> Instrument [name = '" + self._instrumentName + "'] <-> Dataset [name = '" + str(dataset.name) + "']")

            if len(dbInvestigations) == 0:
                logging.error("No investigation entry found: try cataloging the raw data first.")
                return
            else:
                investigation = dbInvestigations[0]
                if len(dbInvestigations)>1:
                    logging.error("Multiple investigation entries found: using the first.")

            logging.debug("Creating dataset: %s" % datetime.now())
            dataset.investigation = investigation
            dataset.sample = investigation.samples[0]
            self._service.create(self._sessionId, dataset)

        elif len(dbDatasets) == 1:
            logging.debug("reduced dataset %s is already cataloged, updating reduced dataset... " % (dataset.name))

            dbDataset = dbDatasets[0]
            # update "one to many" relationships
            if hasattr(dbDataset, "datafiles"):
                dfs = getattr(dbDataset, "datafiles")
                self._service.deleteMany(self._sessionId, dfs)

            for df in datafiles:
                df.dataset = dbDataset
            self._service.createMany(self._sessionId, datafiles)

        else:
            logging.error("ERROR, there should be only one dataset per run number per type reduced")
