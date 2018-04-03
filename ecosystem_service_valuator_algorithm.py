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
        email                : philip.ribbens@gmail.com
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
from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsField)


class EcosystemServiceValuatorAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    OUTPUT = 'OUTPUT'
    INPUT = 'INPUT'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        #input raster
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                self.tr('Input raster layer')
            )
        )

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "input feature",
                self.tr('Mask layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "input raster summary csv",
                self.tr('Raster Summary CSV'),
                [QgsProcessing.TypeFile]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "input esv csv",
                self.tr('Ecosystem Service Values CSV'),
                [QgsProcessing.TypeFile]
            )
        )
        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        raster_summary_source = self.parameterAsSource(parameters, "input raster summary csv", context)
        esv_source = self.parameterAsSource(parameters, "input esv csv", context)

        #appen
        unique_eco_services = esv_source.uniqueValues(2)
        print(unique_eco_services)

        sink_fields = raster_summary_source.fields()

        for eco_service in unique_eco_services:
            min_field_str = eco_service.lower() + "_" + "min"
            max_field_str = eco_service.lower() + "_" + "max"
            mean_field_str = eco_service.lower() + "_" + "mean"
            sink_fields.append(QgsField(min_field_str))
            sink_fields.append(QgsField(max_field_str))
            sink_fields.append(QgsField(mean_field_str))

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT,
                context, sink_fields, raster_summary_source.wkbType(), raster_summary_source.sourceCrs())

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / raster_summary_source.featureCount() if raster_summary_source.featureCount() else 0
        features = raster_summary_source.getFeatures()

        #print("hello")
        #print("feature count: " + str(source.featureCount()))
        #print_str = "features: "

        for current, feature in enumerate(features):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            # Add a feature in the sink
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            #print_str = print_str + ", " + str(current) + ": " + str(feature.attributes()[0])

            # Update the progress bar
            feedback.setProgress(int(current * total))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Ecosystem Service Valuator'

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
        return 'Ecosystem Service Valuator'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return EcosystemServiceValuatorAlgorithm()
