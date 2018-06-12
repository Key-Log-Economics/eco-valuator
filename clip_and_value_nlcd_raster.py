# -*- coding: utf-8 -*-

"""
/***************************************************************************
 EcoValuator
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

import os
import csv
import processing

from PyQt5.QtCore import (QCoreApplication,
                          QFileInfo
                          )

from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFeatureSink,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsFeatureSink,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingOutputLayerDefinition,
                       QgsRasterLayer,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterRasterDestination
                       )

from .parser import HTMLTableParser

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
__esv_data_location__ = os.path.join(__location__, "esv_data")


class ClipAndValueNLCDRaster(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_RASTER = 'INPUT_RASTER'
    MASK_LAYER = 'MASK_LAYER'
    CLIPPED_RASTER = 'CLIPPED_RASTER'
    CLIPPED_RASTER_FILENAME_DEFAULT = 'Output clipped raster'
    HTML_OUTPUT_PATH = 'HTML_OUTPUT_PATH'
    INPUT_ESV = 'INPUT_ESV'
    # Getting list of all CSVs in the esv_data directory
    ESV_CSVS = []
    for file in os.listdir(__esv_data_location__):
        if file.endswith(".csv"):
            ESV_CSVS.append(file)
    OUTPUT_RASTER_SUMMARY_TABLE = 'OUTPUT_RASTER_SUMMARY_TABLE'
    OUTPUT_RASTER_SUMMARY_TABLE_FILENAME_DEFAULT = 'Output table of raster unique values'
    OUTPUT_ESV_TABLE = 'OUTPUT_ESV_TABLE'
    OUTPUT_ESV_TABLE_FILENAME_DEFAULT = 'Output ESV table'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm
        """
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                self.tr('Input NLCD raster')
            )
        )
        # Input vector to be mask for raster
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.MASK_LAYER,
                self.tr('Input mask layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_ESV,
                self.tr('Input table of ESV research data'),
                self.ESV_CSVS
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.CLIPPED_RASTER,
                self.tr('Clipped raster layer'),
                ".tif"
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.HTML_OUTPUT_PATH,
                self.tr('Place to save intermediate html file')
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_ESV_TABLE,
                self.tr(self.OUTPUT_ESV_TABLE_FILENAME_DEFAULT)
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        log = feedback.setProgressText

        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)

        # Check that the input raster has been loaded correctly
        if not input_raster.isValid():
            error_message = "Layer failed to load."
            feedback.reportError(error_message)
            return {'error': error_message}

        # Check that the input raster is in the right CRS
        input_raster_crs = input_raster.crs().authid()
        if input_raster_crs == "EPSG:102003":
            log("The input raster is in the right CRS: EPSG:102003. Check")
        else:
            error_message = "The input raster isn't in the right CRS. It must be in EPSG:102003. The one you input was in " + str(input_raster_crs) + "."
            feedback.reportError(error_message)
            log("")
            return {'error': error_message}

        # Check that the input raster has the right pixel size
        units_per_pixel_x = input_raster.rasterUnitsPerPixelX()
        units_per_pixel_y = input_raster.rasterUnitsPerPixelY()
        if units_per_pixel_x != 30 or units_per_pixel_y != 30:
            if round(units_per_pixel_x) == 30 and round(units_per_pixel_y) == 30:
                feedback.pushDebugInfo("Your input raster pixels weren't exactly 30x30 meters, but were close enough that the program will continue to run. Your input raster pixels were " + str(units_per_pixel_x) + "x" + str(units_per_pixel_y) + ".")
            else:
                error_message = "The input raster should have 30x30 meter pixels. The one you input has " + str(units_per_pixel_x) + "x" + str(units_per_pixel_y) + "."
                feedback.reportError(error_message)
                log("")
                return {'error': error_message}
        else:
            log("The input raster's pixel size is correct: 30x30. Check")

        input_vector = self.parameterAsVectorLayer(parameters, self.MASK_LAYER, context)

        # Check that the input vector is in the right CRS
        input_vector_crs = input_vector.crs().authid()
        if input_vector_crs == "EPSG:102003":
            log("The input mask layer is in the right CRS: EPSG:102003. Check")
        else:
            error_message = "The input mask layer isn't in the right CRS. It must be in EPSG:102003. The one you input was in " + str(input_vector_crs) + "."
            feedback.reportError(error_message)
            log("")
            return {'error': error_message}

        # Get the input table of esv research data into a list of lists so we can work with it
        input_esv_index = self.parameterAsEnum(parameters, self.INPUT_ESV, context)
        input_esv_file = self.ESV_CSVS[input_esv_index]
        input_esv_table = []
        with open(os.path.join(__esv_data_location__, input_esv_file), newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                input_esv_table.append(row)

        # Check to make sure the input table of esv research data has 6 columns
        if len(input_esv_table[0]) != 6:
            error_message = "The Input table of ESV research data should have 6 columns, the one you input has " + str(len(input_esv_table[0]))
            feedback.reportError(error_message)
            log("")
            return {'error': error_message}
        else:
            log("Input table of ESV research data has 6 columns. Check")

        # Check to make sure the input table of esv research data has NLCD codes in its first column
        input_esv_table_column_1_values = [row[0] for row in input_esv_table]
        nlcd_codes = ['11', '21', '22', '23', '24', '31', '41', '42', '43', '52', '71', '81', '82', '90', '95']
        if all(str(i) in nlcd_codes for i in input_esv_table_column_1_values[1:]):
            log("The input input table of esv research data has the correct NLCD codes in the first column. Check")
        else:
            error_message = "The first column of the input table of esv research data isn't all legitimate NLCD codes. They must all be one of these values: " + str(nlcd_codes) + ". The table you input had these values: " + str(input_esv_table_column_1_values[1:])
            feedback.reportError(error_message)
            log("")
            return {'error': error_message}

        # Append input raster and input vector filenames to end of output clipped raster filename
        if isinstance(parameters['CLIPPED_RASTER'], QgsProcessingOutputLayerDefinition):
            dest_name = input_raster.name() + "-CLIPPED_BY-" + input_vector.name()
            setattr(parameters['CLIPPED_RASTER'], 'destinationName', dest_name)
        elif isinstance(parameters['CLIPPED_RASTER'], str):  # for some reason when running this as part of a model parameters['OUTPUT_ESV_TABLE'] isn't a QgsProcessingOutputLayerDefinition object, but instead is just a string
            if parameters['CLIPPED_RASTER'][0:7] == "memory:":
                parameters['CLIPPED_RASTER'] = input_raster.name() + "-CLIPPED_BY-" + input_vector.name()

        clipped_raster_destination = self.parameterAsOutputLayer(parameters, self.CLIPPED_RASTER, context)

        # Clip the input raster by the input mask layer (vector)
        log("Clipping raster...")
        processing.run("gdal:cliprasterbymasklayer", {'INPUT': input_raster, 'MASK': input_vector.source(), 'ALPHA_BAND': False, 'CROP_TO_CUTLINE': True, 'KEEP_RESOLUTION': False, 'DATA_TYPE': 0, 'OUTPUT': clipped_raster_destination}, context=context, feedback=feedback)
        log("Done clipping raster.")

        # Summarize the raster, i.e. calculate the pixel counts and total area for each NLCD value
        log("Summarizing raster...")
        html_output_path = self.parameterAsFileOutput(parameters, self.HTML_OUTPUT_PATH, context)
        clipped_raster = QgsRasterLayer(clipped_raster_destination)
        processing.run("native:rasterlayeruniquevaluesreport", {'INPUT': clipped_raster, 'BAND': 1, 'OUTPUT_HTML_FILE': html_output_path}, context=context, feedback=feedback)
        log("Done summarizing raster.")

        log("Calculating ecosystem service values for clipped raster...")
        # Process html output of rasterlayeruniquevaluesreport algorithm into a table so we can do stuff with it
        input_html = open(html_output_path, 'r', encoding='latin1')
        input_html_string = input_html.read()
        # Instantiate the parser and then parse the table elements into a python list of lists
        p = HTMLTableParser()
        p.feed(input_html_string)
        raster_summary_table = p.tables[0]
        del raster_summary_table[0]  # Delete the header row

        # Check to make sure the input raster is an NLCD raster, i.e. has the right kinds of pixel values
        raster_summary_table_column_1_values = [row[0] for row in raster_summary_table]
        if all(str(i) in nlcd_codes for i in raster_summary_table_column_1_values):
            log("The input raster has the correct NLCD codes for pixel values. Check")
        else:
            error_message = "The input raster's pixels aren't all legitimate NLCD codes. They must all be one of these values: " + str(nlcd_codes) + ". The raster you input had these values: " + str(raster_summary_table_column_1_values)
            feedback.reportError(error_message)
            log("")
            return {'error': error_message}

        # Create list of fields (i.e. column names) for the output esv table
        output_esv_table_fields = QgsFields()
        output_esv_table_fields.append(QgsField("nlcd_code"))
        output_esv_table_fields.append(QgsField("nlcd_description"))
        output_esv_table_fields.append(QgsField("pixel_count"))
        output_esv_table_fields.append(QgsField("area_m2"))
        # Create fields for the min, max, and mean of each unique
        # ecosystem service (i.e. water, recreation, etc)
        unique_eco_services = set([row[2] for row in input_esv_table[1:]])
        for eco_service in unique_eco_services:
            min_field_str = eco_service.lower().replace(" ", "-").replace(",", "") + "_" + "min"
            mean_field_str = eco_service.lower().replace(" ", "-").replace(",", "") + "_" + "mean"
            max_field_str = eco_service.lower().replace(" ", "-").replace(",", "") + "_" + "max"
            output_esv_table_fields.append(QgsField(min_field_str))
            output_esv_table_fields.append(QgsField(mean_field_str))
            output_esv_table_fields.append(QgsField(max_field_str))
        # Then append three more columns for the totals
        output_esv_table_fields.append(QgsField("total_min"))
        output_esv_table_fields.append(QgsField("total_mean"))
        output_esv_table_fields.append(QgsField("total_max"))

        # Append input raster filename to end of output esv table filename
        if isinstance(parameters['OUTPUT_ESV_TABLE'], QgsProcessingOutputLayerDefinition):
            dest_name = self.OUTPUT_ESV_TABLE_FILENAME_DEFAULT.replace(" ", "_") + "-" + input_esv_file.split(".")[0] + "-" + parameters['CLIPPED_RASTER'].destinationName
            setattr(parameters['OUTPUT_ESV_TABLE'], 'destinationName', dest_name)
        elif isinstance(parameters['OUTPUT_ESV_TABLE'], str):  # for some reason when running this as part of a model parameters['OUTPUT_ESV_TABLE'] isn't a QgsProcessingOutputLayerDefinition object, but instead is just a string
            if parameters['OUTPUT_ESV_TABLE'][0:7] == "memory:":
                parameters['OUTPUT_ESV_TABLE'] = parameters['OUTPUT_ESV_TABLE'].replace(" ", "_") + "-" + input_esv_file.split(".")[0] + "-" + parameters['CLIPPED_RASTER'].destinationName

        # Create the feature sink for the output esv table, i.e. the place where we're going to start
        # putting our output data. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_ESV_TABLE, context, output_esv_table_fields)

        result = {self.CLIPPED_RASTER: clipped_raster_destination,
                  self.OUTPUT_ESV_TABLE: dest_id}

        # Compute the number of steps to display within the progress bar
        total = 100.0 / len(raster_summary_table) if len(raster_summary_table) else 0

        area_units_conversion_factor = 0.0001  # Going from meters squared to hectares

        # Populate the output table (feature sink) with values
        for raster_summary_current, raster_summary_row in enumerate(raster_summary_table):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            nlcd_code = raster_summary_row[0]
            pixel_count = raster_summary_row[1]
            area = raster_summary_row[2]

            new_feature = QgsFeature(output_esv_table_fields)
            new_feature.setAttribute(0, nlcd_code)
            new_feature.setAttribute(2, pixel_count)
            new_feature.setAttribute(3, area)

            total_min = 0
            total_mean = 0
            total_max = 0

            for row in input_esv_table:
                if row[0] == nlcd_code:
                    new_feature.setAttribute(1, row[1])  # Set the value of the second column in the output table, the nlcd description
                    input_es_name = row[2].lower().replace(" ", "-")
                    for field_index in output_esv_table_fields.allAttributesList():
                        output_es = output_esv_table_fields.field(field_index).name().split("_")
                        output_es_name = output_es[0].lower()
                        if len(output_es) > 1:
                            output_es_stat = output_es[1].lower()
                            if input_es_name == output_es_name:
                                if output_es_stat == "min":
                                    nlcd_es_min = float(row[3].replace(',', '').replace('$', ''))*float(area)*float(area_units_conversion_factor)
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(nlcd_es_min))
                                    total_min = total_min + nlcd_es_min
                                elif output_es_stat == "mean":
                                    nlcd_es_mean = float(row[4].replace(',', '').replace('$', ''))*float(area)*float(area_units_conversion_factor)
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(nlcd_es_mean))
                                    total_mean = total_mean + nlcd_es_mean
                                elif output_es_stat == "max":
                                    nlcd_es_max = float(row[5].replace(',', '').replace('$', ''))*float(area)*float(area_units_conversion_factor)
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(nlcd_es_max))
                                    total_max = total_max + nlcd_es_max
                            elif output_es_name == "total":
                                if output_es_stat == "min":
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(total_min))
                                elif output_es_stat == "mean":
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(total_mean))
                                elif output_es_stat == "max":
                                    new_feature.setAttribute(field_index, '${:,.0f}'.format(total_max))

            # Add the feature to the sink
            sink.addFeature(new_feature, QgsFeatureSink.FastInsert)

            # Update the progress bar
            feedback.setProgress(int(raster_summary_current * total))
        log("Done calculating ecosystem service values for clipped raster.")

        # Return the results of the algorithm, which includes the clipped raster
        # and the output esv table
        return result

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Step 1: Clip and value NLCD raster'

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
        return self.tr("This <strong>algorithm</strong> does 3 <i>things</i>:\n <ol><li>Clips the Input NLCD raster by the Input mask layer (which should represent the user’s region of interest).</li><li>Calculates how much area each type of land cover accounts for in the now-clipped NLCD raster.</li><li>Multiplies those areas by each of the associated ecosystem service values (ESV) in the Input table of ESV research data.</li></ol> The output includes the clipped raster and a table of aggregate ESV for each land cover type in study region.\n \nThe input NLCD raster covers the entire continental US and must be in CRS: EPSG: 102003 (CONUS in order to successfully execute the clip to the mask layer. This raster should also have 30x30 meter pixels and have NLCD values as its pixel values.\n Input mask layer: This vector is your area of interest used to clip the NLDC data. It too should be in EPSG:102003.\n Input table of ESV research data: This table of data comes pre-loaded with the plugin and provides the per-hectare-per-year minimum, average, and maximum dollar value estimates for each land cover type and ecosystem service. These figures are also adjusted for the exchange rate and inflation. These figures are derived from an extensive literature review. See Help for details.\n Place to save intermediate html file: Optional. The algorithm does not require that the .html be saved separately.\n Output ESV table: This table contains NLCD land cover values and descriptions as rows, and associated ecosystem service values broken into minimum, mean, and maximum values as columns. Note that many NULL values will appear in the table due to a lack of existing research on certain ecosystem services in each land cover type, and NULL does not correspond to a dollar value of 0. See “Help” for more information on the National Land Cover Database and error issue identification.")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def helpUrl(self):
        """
        Returns the location of the help file for this algorithm. This is the
        location that will be followed when the user clicks the Help button
        in the algorithm's UI.
        """
        return "file:///%s/help/index.html" % os.path.dirname(os.path.realpath(__file__))

    def createInstance(self):
        return ClipAndValueNLCDRaster()
