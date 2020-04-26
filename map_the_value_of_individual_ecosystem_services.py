#NEW
# -*- coding: utf-8 -*-

"""
/***************************************************************************
 EcoValuator
                                 A QGIS plugin
 Calculate ecosystem service values for a given area
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-04-02
        copyright            : (C) 2018 by Key-Log Economics
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

__author__ = 'Key-Log Economics'
__date__ = '2018-04-02'
__copyright__ = '(C) 2018 by Key-Log Economics'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import numpy as np
from numpy import copy
import processing

from os.path import splitext

from PyQt5.QtGui import *
from qgis.utils import *
from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterDestination,
                       QgsRasterFileWriter,
                       QgsRasterLayer,
                       QgsProcessingParameterString,
                       QgsProcessingParameterNumber,
                       QgsProcessingOutputLayerDefinition,
                       QgsProcessingParameterEnum,
                       QgsMapLayerStyle,
                       QgsProject,
                       QgsColorRampShader,
                       QgsRasterShader,
                       QgsRasterBandStats,
                       QgsSingleBandPseudoColorRenderer
                      )

from .appinter import (Raster, App)
from .eco_valuator_classes import LULC_dataset, ESV_dataset


class MapTheValueOfIndividualEcosystemServices(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_ESV_FIELD = 'INPUT_ESV_FIELD'
    INPUT_ESV_STAT = 'INPUT_ESV_STAT'
    STATS_MAP = {'Minimum':'Min', 'Average':'Avg', 'Maximum':'Max'}
    STATS = list(STATS_MAP)
    OUTPUT_RASTER = 'OUTPUT_RASTER'
    OUTPUT_RASTER_FILENAME_DEFAULT = 'Output esv raster'
    
    INPUT_LULC_SOURCE = 'INPUT_LULC_SOURCE'

    with ESV_dataset() as esv:
        LULC_SOURCES = esv.get_lulc_sources()
        INPUT_ESV_FIELD_OPTIONS = esv.get_ecosystem_service_names()

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm
        """
        # Add a parameter for the clipped raster layer
        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_LULC_SOURCE,
                self.tr('Select land use/land cover data source'),
                self.LULC_SOURCES
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                self.tr('Input clipped raster layer')
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_ESV_FIELD,
                self.tr('Choose ecosystem service of interest'),
                self.INPUT_ESV_FIELD_OPTIONS
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_ESV_STAT,
                self.tr('Choose ecosystem Service Value Level'),
                self.STATS
            )
        )

        # Add a parameter for the output raster layer
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_RASTER,
                self.tr(self.OUTPUT_RASTER_FILENAME_DEFAULT)
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        log = feedback.setProgressText
        
        input_lulc_source_index = self.parameterAsEnum(parameters, self.INPUT_LULC_SOURCE, context)
        input_lulc_source = self.LULC_SOURCES[input_lulc_source_index]
        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        input_esv_field_index = self.parameterAsEnum(parameters, self.INPUT_ESV_FIELD, context)
        input_esv_field = self.INPUT_ESV_FIELD_OPTIONS[input_esv_field_index]
        input_esv_stat_index = self.parameterAsEnum(parameters, self.INPUT_ESV_STAT, context)
        input_esv_stat_full_name = self.STATS[input_esv_stat_index]
        input_esv_stat = self.STATS_MAP[input_esv_stat_full_name]

        log(f"ESV chosen: {input_esv_field}")

        #Labeling output layer in legend   
        if isinstance(parameters['OUTPUT_RASTER'], QgsProcessingOutputLayerDefinition):
            if input_esv_field != 'protection from extreme events':         #'protection from exteme events' is too long for legend in step 3 so it is shortened here
                if input_esv_stat == 'min':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Minimum Value - {input_esv_field}')
                elif input_esv_stat == 'max':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Maximum Value - {input_esv_field}')
                elif input_esv_stat == 'avg':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Average Value - {input_esv_field}')
            else:
                if input_esv_stat == 'min':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Minimum Value - extreme event protection')
                elif input_esv_stat == 'max':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Maximum Value - extreme event protection')
                elif input_esv_stat == 'avg':
                    setattr(parameters['OUTPUT_RASTER'], 'destinationName', f'Average Value - extreme event protection')


        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        output_raster_destination = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)

        result = {self.OUTPUT_RASTER: output_raster_destination}

        """Check output file format to make sure it is a geotiff"""

        output_format = QgsRasterFileWriter.driverForExtension(splitext(output_raster_destination)[1])

        if not output_format or output_format.lower() != "gtiff":
            error_message = "CRITICAL: Currently only GeoTIFF output format allowed, exiting!"
            feedback.reportError(error_message)
            return({'error': error_message})
        else:
            message = "Output file is GeoTIFF. Check"
            log(message)

        #Make instance of LULC dataset from clipped layer here
        LULC_raster = LULC_dataset(input_lulc_source, input_raster)
        
        # Check to make sure all land use codes are valid 
        valid = LULC_raster.is_valid()
        if isinstance(valid, str):
            #If is instance returns a string it is not valid. The string contains the error message
            error_message = valid
            feedback.reportError(error_message)
            return {'error': error_message}

        # Get reclassify table for selected parameters
        ESV_data = ESV_dataset()
        reclass_table = ESV_data.make_reclassify_table(LULC_raster.cell_size(),
                                                       input_lulc_source,
                                                       input_esv_stat,
                                                       input_esv_field)

        # Perform reclassification
        reclassify_params = {'INPUT_RASTER':input_raster,
        'RASTER_BAND':1,
        'TABLE':reclass_table,
        'NO_DATA':-9999,
        'RANGE_BOUNDARIES':0,
        'NODATA_FOR_MISSING':True,
        'DATA_TYPE':6,
        'OUTPUT':output_raster_destination}

        processing.run("native:reclassifybytable", reclassify_params)

        # Get min and max values for quintile calculations

        output_raster = self.parameterAsRasterLayer(parameters, self.OUTPUT_RASTER, context)

        provider = output_raster.dataProvider()
        stats = provider.bandStatistics(1, QgsRasterBandStats.All)
        output_min_val = stats.minimumValue
        output_max_val = stats.maximumValue

        #must add raster to iface so that is becomes active layer, then symbolize it in next step
        iface.addRasterLayer(output_raster_destination)
        log("Symbolizing Output")
        
        #grabs active layer and data from that layer
        layer = iface.activeLayer()
        provider = layer.dataProvider()
        extent = layer.extent()

        # Compute quintile ranges for symbolizing output raster
        value_range = list(range(int(output_min_val), int(output_max_val)+1))
        if value_range[0] == 0:
            # Deletes 0 value from value range so as not to skew shading in results
            value_range.pop(0)

        #we will categorize pixel values into 5 quintiles, based on value_range of raster layer
        #defining min and max values for each quintile. 
        #Also, values are rounded to 2 decimal places
        first_quintile_max = round(np.percentile(value_range, 20), 2)
        first_quintile_min = round(output_min_val, 2)
        second_quintile_max = round(np.percentile(value_range, 40), 2)
        second_quintile_min = round((first_quintile_max + .01), 2)
        third_quintile_max = round(np.percentile(value_range, 60), 2)
        third_quintile_min = round((second_quintile_max + .01), 2)
        fourth_quintile_max = round(np.percentile(value_range, 80), 2)
        fourth_quintile_min = round((third_quintile_max + .01), 2)
        fifth_quintile_max = round(np.percentile(value_range, 100), 2)
        fifth_quintile_min = round((fourth_quintile_max + .01), 2)

        """Takes values for each quintile and builds raster shader with discrete color for each quintile.
        Unique color ramp chosen for each ESV value. I tried to be intuitive with the colors.
        Lastly, shades output in QGIS."""

        color_ramps = {
                        'green':(QColor(255, 255, 255, .5), QColor(204, 255, 204), QColor(153, 255, 153), QColor(51, 255, 51), QColor(0, 204, 0), QColor(0, 102, 0)),
                        'light_blue':(QColor(255, 255, 255, .5), QColor(204, 255, 255), QColor(153, 255, 255), QColor(51, 255, 255), QColor(0, 204, 204), QColor(0,102,102)),
                        'green':(QColor(255, 255, 255, .5), QColor(204, 255, 229), QColor(153, 255, 204), QColor(51, 255, 153), QColor(0, 204, 102), QColor(0, 102, 51)),
                        'orange':(QColor(255, 255, 255, .5), QColor(255, 229, 204), QColor(255, 204, 153), QColor(255, 153, 51), QColor(204, 102, 0), QColor(102, 51, 0)),
                        'brown':(QColor(255, 255, 255, .5), QColor(220,187,148), QColor(198,168,134), QColor(169,144,115), QColor(138,117,93), QColor(100,85,67)),
                        'pink':(QColor(255, 255, 255, .5), QColor(255,204,229), QColor(255,153,204), QColor(255,51,153), QColor(204,0,102), QColor(102,0,51)),
                        'yellow':(QColor(255, 255, 255, .5), QColor(255,255,204), QColor(255,255,153), QColor(255,255,51), QColor(204,204,0), QColor(102,102,0)),
                        'gray_black':(QColor(255, 255, 255, .5), QColor(224,224,224), QColor(192,192,192), QColor(128,128,128), QColor(64,64,64), QColor(0,0,0)),
                        'purple':(QColor(255, 255, 255, .5), QColor(229,204,255), QColor(204,153,255), QColor(153,51,255), QColor(102,0,204), QColor(51,0,102)),
                        'red':(QColor(255, 255, 255, .5), QColor(255,102,102), QColor(255,51,51), QColor(255,0,0), QColor(204,0,0), QColor(153,0,0)),
                        'brown':(QColor(255, 255, 255, .5), QColor(220,187,148), QColor(198,168,134), QColor(169,144,115), QColor(138,117,93), QColor(100,85,67)),
                        'blue_purple':(QColor(255, 255, 255, .5), QColor(204,204,255), QColor(153,153,255), QColor(51,51,255), QColor(0,0,204), QColor(0,0,102)),
                        'medium_blue':(QColor(255, 255, 255, .5), QColor(204,229,255), QColor(153,204,255), QColor(51,153,205), QColor(0,102,204), QColor(0,51,102))
                    }

        # map the ecosystem service types to the color ramp options
        color_ramp_map = {k:v for k,v in zip(self.INPUT_ESV_FIELD_OPTIONS,color_ramps.values())}
        colors = color_ramp_map[input_esv_field]

        raster_shader = QgsColorRampShader()
        raster_shader.setColorRampType(QgsColorRampShader.Discrete)           #Shading raster layer with QgsColorRampShader.Discrete
        colors_list = [QgsColorRampShader.ColorRampItem(0, QColor(255, 255, 255, .5), 'No Value'), \
                    QgsColorRampShader.ColorRampItem(first_quintile_max, colors[0], f"${first_quintile_min}0 - ${first_quintile_max}0"), \
                    QgsColorRampShader.ColorRampItem(second_quintile_max, colors[1], f"${second_quintile_min} - ${second_quintile_max}0"), \
                    QgsColorRampShader.ColorRampItem(third_quintile_max, colors[2], f"${third_quintile_min} - ${third_quintile_max}0"), \
                    QgsColorRampShader.ColorRampItem(fourth_quintile_max, colors[3], f"${fourth_quintile_min} - ${fourth_quintile_max}0"), \
                    QgsColorRampShader.ColorRampItem(fifth_quintile_max, colors[4], f"${fifth_quintile_min} - ${fifth_quintile_max}0")]       

        raster_shader.setColorRampItemList(colors_list)         #applies colors_list to raster_shader
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(raster_shader)       

        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)    #renders selected raster layer
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        
    
    
        log(self.tr(f"Adding final raster to map."))
        #need to add result from gdal:rastercalculator to map (doesn't happen automatically)
        
        
        log(self.tr("Done!\n"))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return result


    def flags(self):
        """
        From documentation: Algorithm is not thread safe and cannot be run in a
        background thread, e.g. algorithms which manipulate the current project,
        layer selections, or with external dependencies which are not thread safe.
        """
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Step 2: Map the value of individual ecosystem services'

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
        return 'EcoValuator'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("This algorithm takes as an Input the clipped NLCD raster from Step 1 and an Input ESV Table, which is the output table from Step 1, and creates a new raster for which the value is the corresponding per-pixel value (minimum, mean, or maximum) of the user-chosen ecosystem service. The new raster is then  given a descriptive name and colored according to the ecosystem service chosen. It's values are divided into even quintiles to emphasize breaks in the data. The user can repeat this step for additional levels (min, mean, max) and ecosystem services.\n Input NLCD raster: This should be the output clipped raster from Step 1, an NLCD layer clipped by a region of interest. \n Input ESV table: This should be the output ESV table from Step 1 and should not be altered. \n Ecosystem service of interest: Specify the ecosystem service you want to map. \n Ecosystem Service Value Level: Choose if you want to map minimum, mean, or maximum values from the ESV table. \n Output esv Raster: Specify an output location for your ESV raster. \n See “Help” for more information on value origins and ecosystem service descriptions.")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def helpUrl(self):
        return "http://www.keylogeconomics.com/ecovaluator.html"

    def createInstance(self):
        return MapTheValueOfIndividualEcosystemServices()