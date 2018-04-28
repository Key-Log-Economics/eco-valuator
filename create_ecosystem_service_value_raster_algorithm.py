# -*- coding: utf-8 -*-

"""
/***************************************************************************
 EcosystemServiceValuator
                                 A QGIS plugin
 Calculate ecosystem service values for a given area
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-04-02
        copyright            : (C) 2018 by Phil Ribbens/Key-Log Economics
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Phil Ribbens/Key-Log Economics'
__date__ = '2018-04-02'
__copyright__ = '(C) 2018 by Phil Ribbens/Key-Log Economics'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import numpy as np
from numpy import copy
import processing

from os.path import splitext

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterDestination,
                       QgsRasterFileWriter,
                       QgsRasterLayer,
                       QgsProcessingParameterString,
                       QgsProcessingParameterNumber
                       )

import appinter

class CreateEcosystemServiceValueRasterAlgorithm(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_NODATA_VALUE = 'INPUT_NODATA_VALUE'
    INPUT_ESV_TABLE = 'INPUT_ESV_TABLE'
    INPUT_ESV_FIELD = 'INPUT_ESV_FIELD'
    OUTPUT_RASTER = 'OUTPUT_RASTER'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm
        """
        # Add a parameter for the clipped raster layer
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                self.tr('Input NLCD raster'),
                ".tif"
            )
        )

        #Add a parameter where the user can specify what the nodata value of
        # the raster they're inputting is.
        # Must be an integer
        # Default is 255
        #This will be used later to make sure that any pixels in the incoming rasterany
        # that have this value will continue to have this value in the output rasterself.
        #It's also used to give this value to any pixels that would otherwise be Null
        # in the output raster
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_NODATA_VALUE,
                self.tr('Nodata value of input raster'),
                QgsProcessingParameterNumber.Integer,
                255
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ESV_TABLE,
                self.tr('Input ESV table'),
                [QgsProcessing.TypeFile]
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_ESV_FIELD,
                self.tr('Input ESV field to create raster for'),
                'total_min'
            )
        )

        # Add a parameter for the output raster layer
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_RASTER,
                self.tr('Output raster layer'),
                ".tif"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        Raster = appinter.Raster
        App = appinter.App

        log = feedback.setProgressText
        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        input_nodata_value = self.parameterAsInt(parameters, self.INPUT_NODATA_VALUE, context)
        input_esv_table = self.parameterAsSource(parameters, self.INPUT_ESV_TABLE, context)
        input_esv_field = self.parameterAsString(parameters, self.INPUT_ESV_FIELD, context)
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        result = { self.OUTPUT_RASTER : output_raster }

        # Check output format
        output_format = QgsRasterFileWriter.driverForExtension(splitext(output_raster)[1])
        if not output_format or output_format.lower() != "gtiff":
            log("CRITICAL: Currently only GeoTIFF output format allowed, exiting!")
            return result

        raster_value_mapping_dict = {}

        input_esv_table_features = input_esv_table.getFeatures()

        for input_esv_table_feature in input_esv_table_features:
            nlcd_code = input_esv_table_feature.attributes()[0]
            try:
                selected_esv = input_esv_table_feature.attribute(input_esv_field)
            except KeyError:
                feedback.reportError("The Input Ecosystem Service Value field you specified doesn't exist in this dataset. Please enter one of the fields that does exist: ")
                feedback.pushDebugInfo(str(input_esv_table.fields().names()[3:]))
                log("")
                return result
            #If there is no ESV for tis particular NLCD-ES combo Then
            # the cell will be Null (i.e. None) and so we're dealing with
            # that below by setting the value to 255, which is the value
            # of the other cells that don't have values (at least for this
            # data)
            if selected_esv is None:
                selected_esv = input_nodata_value
            #If it's not null then we need to convert the total ESV for
            # the whole area covered by that land cover (which is in USD/hectare)
            # to the per pixel ESV (USD/pixel)
            else:
                num_pixels = input_esv_table_feature.attributes()[1]
                selected_esv = int(selected_esv) / 0.0001 / int(num_pixels)
            raster_value_mapping_dict.update({int(nlcd_code): selected_esv})

        # Output raster
        log(self.tr("Reading input raster into numpy array ..."))
        #use isValid() somewhere in here to make sure the incoming raster layer is valid
        grid = Raster.to_numpy(input_raster, band=1, dtype=int)
        log(self.tr("Array read"))
        log(self.tr("Mapping values"))
        output_array = self.mapValues(grid, raster_value_mapping_dict)   #takes about 8 seconds
        log(self.tr("Values mapped"))
        log(self.tr("Saving output raster ..."))
        Raster.numpy_to_file(output_array, output_raster, src=str(input_raster.source()))

        log(self.tr("Done!\n"))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return result

    def mapValues(self, numpy_array, dictionary):
        output_array = copy(numpy_array)
        for key, value in dictionary.items():
            output_array[numpy_array==key] = value
        return output_array

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Create ESV raster'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Ecosystem service valuator'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateEcosystemServiceValueRasterAlgorithm()
