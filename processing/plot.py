#! /usr/bin/env python

'''
License:
  "NASA Open Source Agreement 1.3"

Description:

History:
  Original Development Jan/2014 by Ron Dilley, USGS/EROS
'''

import os
import sys
import glob
import shutil
import datetime
import calendar
import subprocess
import traceback
from cStringIO import StringIO
from argparse import ArgumentParser
from collections import defaultdict
from matplotlib import pyplot as mpl_plot
from matplotlib import dates as mpl_dates
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
import numpy as np
import logging

# espa-common objects and methods
from espa_constants import *


# Setup the default colors
# Can override them from the command line
SENSOR_COLORS = dict()
SENSOR_COLORS['Terra'] = '#664400'  # Some Brown kinda like dirt
SENSOR_COLORS['Aqua'] = '#00cccc'  # Some cyan like blue color
SENSOR_COLORS['LT4'] = '#cc3333'  # A nice Red
SENSOR_COLORS['LT5'] = '#0066cc'  # A nice Blue
SENSOR_COLORS['LE7'] = '#00cc33'  # An ok Green
BG_COLOR = '#f3f3f3'  # A light gray

# Setup the default marker
# Can override them from the command line
MARKER = (1, 3, 0)  # Better circle than 'o'
MARKER_SIZE = 5.0   # A good size for the circle or diamond

# Specify a base number of days to expand the plot date range
# This helps keep data points from being placed on the plot border lines
TIME_DELTA_5_DAYS = datetime.timedelta(days=5)

# Define the data ranges and output ranges for the plotting
# Must match the UPPER_BOUND and LOWER_BOUND in settings.py
# The toplevel keys are used as search strings into the band_type displayed
# names, so they need to match unique(enough) portions of those strings
# ----------------------------------------------------------------------------
#          DATA_MAX: The maximum value represented in the data.
#          DATA_MIN: The minimum value represented in the data.
#         SCALE_MAX: The DATA_MAX is scaled to this value.
#         SCALE_MIN: The DATA_MIN is scaled to this value.
#       DISPLAY_MAX: The maximum value to display on the plot.
#       DISPLAY_MIN: The minimum value to display on the plot.
#    MAX_N_LOCATORS: The maximum number of spaces between Y-axis tick marks.
#                    This should be adjusted so that the tick marks fall on
#                    values that display nicely.  Due to having some buffer
#                    added to the display minimum and maximum values, the
#                    value chosen for this parameter should include the space
#                    between the top and the top tick mark as well as the
#                    bottom and bottom tick mark. (i.e. Add two)
# ----------------------------------------------------------------------------
BAND_TYPE_DATA_RANGES = {
    'SR': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': 0.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': 0.0,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': 0.0,
        'MAX_N_LOCATORS': 12
    },
    'TOA': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': 0.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': 0.0,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': 0.0,
        'MAX_N_LOCATORS': 12
    },
    'NDVI': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'EVI': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'SAVI': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'MSAVI': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'NBR': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'NBR2': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'NDMI': {
        'DATA_MAX': 10000.0,
        'DATA_MIN': -1000.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': -0.1,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': -0.1,
        'MAX_N_LOCATORS': 13
    },
    'LST': {
        'DATA_MAX': 65535.0,
        'DATA_MIN': 7500.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': 0.0,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': 0.0,
        'MAX_N_LOCATORS': 12
    },
    'Emis': {
        'DATA_MAX': 255.0,
        'DATA_MIN': 1.0,
        'SCALE_MAX': 1.0,
        'SCALE_MIN': 0.0,
        'DISPLAY_MAX': 1.0,
        'DISPLAY_MIN': 0.0,
        'MAX_N_LOCATORS': 12
    }
}


# ============================================================================
def execute_cmd(cmd):
    '''
    Description:
      Execute a command line and return SUCCESS or ERROR

    Returns:
        output - The stdout and/or stderr from the executed command.
    '''

    output = ''
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, shell=True)
        output = proc.communicate()[0]

        if proc.returncode < 0:
            message = "Application terminated by signal [%s]" % cmd
            raise Exception(message)

        if proc.returncode != 0:
            message = "Application failed to execute [%s]" % cmd
            raise Exception(message)

        application_exitcode = proc.returncode >> 8
        if application_exitcode != 0:
            message = "Application [%s] returned error code [%d]" \
                % (cmd, application_exitcode)
            raise Exception(message)

    finally:
        del proc

    return output
# END - execute_cmd


# =============================================================================
def scp_transfer_file(source_host, source_file,
                      destination_host, destination_file):
    '''
    Description:
      Using SCP transfer a file from a source location to a destination
      location.

    Note:
      - It is assumed ssh has been setup for access between the localhost
        and destination system
      - If wild cards are to be used with the source, then the destination
        file must be a directory.  ***No checking is performed in this code***
    '''

    logger = logging.getLogger(__name__)

    cmd = ['scp', '-q', '-o', 'StrictHostKeyChecking=no', '-c', 'arcfour',
           '-C']

    # Build the source portion of the command
    # Single quote the source to allow for wild cards
    if source_host == 'localhost':
        cmd.append(source_file)
    elif source_host != destination_host:
        # Build the SCP command line
        cmd.append("'%s:%s'" % (source_host, source_file))

    # Build the destination portion of the command
    cmd.append('%s:%s' % (destination_host, destination_file))

    cmd = ' '.join(cmd)

    # Transfer the data and raise any errors
    output = ''
    try:
        output = execute_cmd(cmd)
    except Exception, e:
        if len(output) > 0:
            logger.info(output)
        logger.error("Failed to transfer data")
        raise e

    logger.info("Transfer complete - SCP")
# END - scp_transfer_file


# ============================================================================
def build_argument_parser():
    '''
    Description:
      Build the command line argument parser
    '''

    # Create a command line argument parser
    description = "Generate plots of the statistics"
    parser = ArgumentParser(description=description)

    parser.add_argument('--debug',
                        action='store_true', dest='debug', default=False,
                        help="turn debug logging on")

    parser.add_argument('--source_host',
                        action='store', dest='source_host',
                        default='localhost',
                        help="hostname where the order resides")

    parser.add_argument('--order_directory',
                        action='store', dest='order_directory',
                        required=True,
                        help="directory on the source host where the order"
                             " resides")

    parser.add_argument('--stats_directory',
                        action='store', dest='stats_directory',
                        default=os.curdir,
                        help="directory containing the statistics")

    parser.add_argument('--terra_color',
                        action='store', dest='terra_color',
                        default=SENSOR_COLORS['Terra'],
                        help="color specification for Terra data")

    parser.add_argument('--aqua_color',
                        action='store', dest='aqua_color',
                        default=SENSOR_COLORS['Aqua'],
                        help="color specification for Aqua data")

    parser.add_argument('--lt4_color',
                        action='store', dest='lt4_color',
                        default=SENSOR_COLORS['LT4'],
                        help="color specification for LT4 data")

    parser.add_argument('--lt5_color',
                        action='store', dest='lt5_color',
                        default=SENSOR_COLORS['LT5'],
                        help="color specification for LT5 data")

    parser.add_argument('--le7_color',
                        action='store', dest='le7_color',
                        default=SENSOR_COLORS['LE7'],
                        help="color specification for LE7 data")

    parser.add_argument('--bg_color',
                        action='store', dest='bg_color', default=BG_COLOR,
                        help="color specification for plot and legend"
                             " background")

    parser.add_argument('--marker',
                        action='store', dest='marker', default=MARKER,
                        help="marker specification for plotted points")

    parser.add_argument('--marker_size',
                        action='store', dest='marker_size',
                        default=MARKER_SIZE,
                        help="marker size specification for plotted points")

    parser.add_argument('--keep',
                        action='store_true', dest='keep', default=False,
                        help="keep the working directory")

    return parser
# END - build_argument_parser


# ============================================================================
def read_stats(stat_file):
    '''
    Description:
      Read the file contents and return as a list of key values
    '''

    with open(stat_file, 'r') as stat_fd:
        for line in stat_fd:
            line_lower = line.strip().lower()
            parts = line_lower.split('=')
            yield(parts)

# END - read_stats


# ============================================================================
def get_mdom_from_ydoy(year, day_of_year):
    '''
    Description:
      Determine month and day_of_month from the year and day_of_year
    '''

    # Convert DOY to month and day
    month = 1
    day_of_month = day_of_year
    while month < 13:
        month_days = calendar.monthrange(year, month)[1]
        if day_of_month <= month_days:
            return (month, day_of_month)
        day_of_month -= month_days
        month += 1
# END - get_mdom_from_ydoy


# ============================================================================
def get_ymds_from_filename(filename):
    '''
    Description:
      Determine the year, month, day_of_month, and sensor from the scene name
    '''

    year = 0
    month = 0
    day_of_month = 0
    sensor = 'unk'

    if filename.startswith('MOD'):
        date_element = filename.split('.')[1]
        year = int(date_element[1:5])
        day_of_year = int(date_element[5:8])
        (month, day_of_month) = get_mdom_from_ydoy(year, day_of_year)
        sensor = 'Terra'

    elif filename.startswith('MYD'):
        date_element = filename.split('.')[1]
        year = int(date_element[1:5])
        day_of_year = int(date_element[5:8])
        (month, day_of_month) = get_mdom_from_ydoy(year, day_of_year)
        sensor = 'Aqua'

    elif 'LT4' in filename:
        year = int(filename[9:13])
        day_of_year = int(filename[13:16])
        (month, day_of_month) = get_mdom_from_ydoy(year, day_of_year)
        sensor = 'LT4'

    elif 'LT5' in filename:
        year = int(filename[9:13])
        day_of_year = int(filename[13:16])
        (month, day_of_month) = get_mdom_from_ydoy(year, day_of_year)
        sensor = 'LT5'

    elif 'LE7' in filename:
        year = int(filename[9:13])
        day_of_year = int(filename[13:16])
        (month, day_of_month) = get_mdom_from_ydoy(year, day_of_year)
        sensor = 'LE7'

    return (year, month, day_of_month, sensor)
# END - get_ymds_from_filename


# ============================================================================
def generate_sensor_stats(stat_name, stat_files):
    '''
    Description:
      Combines all the stat files for one sensor into one csv file.
    '''

    logger = logging.getLogger(__name__)

    stats = dict()

    # Fix the output filename
    out_filename = stat_name.replace(' ', '_').lower()
    out_filename = ''.join([out_filename, '_stats.csv'])

    # Read each file into a dictionary
    for stat_file in stat_files:
        stats[stat_file] = \
            dict((key, value) for (key, value) in read_stats(stat_file))

    stat_data = list()
    # Process through and create records
    for filename, obj in stats.items():
        logger.debug(filename)
        # Figure out the date for stats record
        (year, month, day_of_month, sensor) = get_ymds_from_filename(filename)
        date = '%04d-%02d-%02d' % (int(year), int(month), int(day_of_month))
        logger.debug(date)

        line = '%s,%s,%s,%s,%s' % (date, obj['minimum'], obj['maximum'],
                                   obj['mean'], obj['stddev'])
        logger.debug(line)

        stat_data.append(line)

    # Create an empty string buffer to hold the output
    temp_buffer = StringIO()

    # Write the file header
    temp_buffer.write('DATE,MINIMUM,MAXIMUM,MEAN,STDDEV')

    # Sort the stats into the buffer
    for line in sorted(stat_data):
        temp_buffer.write('\n')
        temp_buffer.write(line)

    # Flush and save the buffer as a string
    temp_buffer.flush()
    data = temp_buffer.getvalue()
    temp_buffer.close()

    # Create the output file
    with open(out_filename, 'w') as output_fd:
        output_fd.write(data)
# END - generate_sensor_stats


# ============================================================================
def scale_data_to_range(in_high, in_low, out_high, out_low, data):
    '''
    Description:
      Scale the values in the data array to the specified output range.
    '''

    # Figure out the ranges
    in_range = in_high - in_low
    out_range = out_high - out_low

    return (out_high - ((out_range * (in_high - data)) / in_range))
# END - scale_data_to_range


# ============================================================================
def generate_plot(plot_name, subjects, band_type, stats, plot_type="Value"):
    '''
    Description:
      Builds a plot and then generates a png formatted image of the plot.
    '''

    logger = logging.getLogger(__name__)

    # Test for a valid plot_type parameter
    # For us 'Range' mean min, max, and mean
    if plot_type not in ('Range', 'Value'):
        error = ("Error plot_type='%s' must be one of ('Range', 'Value')"
                 % plot_type)
        raise ValueError(error)

    # Configuration for the dates
    auto_date_locator = mpl_dates.AutoDateLocator()
    auto_date_formatter = mpl_dates.AutoDateFormatter(auto_date_locator)

    # Create the subplot objects
    fig = mpl_plot.figure()

    # Adjust the figure size
    fig.set_size_inches(11, 8.5)

    min_plot = mpl_plot.subplot(111, axisbg=BG_COLOR)

    # Determine which ranges to use for scaling the data before plotting
    use_data_range = ''
    for range_type in BAND_TYPE_DATA_RANGES:
        if band_type.startswith(range_type):
            use_data_range = range_type
            break
    # Make sure the band_type has been coded (help the developer)
    if use_data_range == '':
        raise ValueError("Error unable to determine 'use_data_range'")

    data_max = BAND_TYPE_DATA_RANGES[use_data_range]['DATA_MAX']
    data_min = BAND_TYPE_DATA_RANGES[use_data_range]['DATA_MIN']
    scale_max = BAND_TYPE_DATA_RANGES[use_data_range]['SCALE_MAX']
    scale_min = BAND_TYPE_DATA_RANGES[use_data_range]['SCALE_MIN']
    display_max = BAND_TYPE_DATA_RANGES[use_data_range]['DISPLAY_MAX']
    display_min = BAND_TYPE_DATA_RANGES[use_data_range]['DISPLAY_MIN']
    max_n_locators = BAND_TYPE_DATA_RANGES[use_data_range]['MAX_N_LOCATORS']

    # ------------------------------------------------------------------------
    # Build a dictionary of sensors which contains lists of the values, while
    # determining the minimum and maximum values to be displayed

    # I won't be here to resolve this
    plot_date_min = datetime.date(9998, 12, 31)
    # Doubt if we have any this old
    plot_date_max = datetime.date(1900, 01, 01)

    sensor_dict = defaultdict(list)
    sensors = list()

    if plot_type == "Range":
        lower_subject = 'mean'  # Since Range force to the mean
    else:
        lower_subject = subjects[0].lower()

    # Convert the list of stats read from the file into a list of stats
    # organized by the sensor and contains a python date element
    for filename, obj in stats.items():
        logger.debug(filename)
        # Figure out the date for plotting
        (year, month, day_of_month, sensor) = \
            get_ymds_from_filename(filename)

        date = datetime.date(year, month, day_of_month)
        min_value = float(obj['minimum'])
        max_value = float(obj['maximum'])
        mean = float(obj['mean'])
        stddev = float(obj['stddev'])

        # Date must be first in the list for later sorting to work
        sensor_dict[sensor].append((date, min_value, max_value, mean, stddev))

        # While we are here figure out...
        # The min and max range for the X-Axis value
        if date < plot_date_min:
            plot_date_min = date
        if date > plot_date_max:
            plot_date_max = date
    # END - for filename

    # Process through the sensor organized dictionary
    for sensor in sensor_dict.keys():
        dates = list()
        min_values = np.empty(0, dtype=np.float)
        max_values = np.empty(0, dtype=np.float)
        mean_values = np.empty(0, dtype=np.float)
        stddev_values = np.empty(0, dtype=np.float)

        # Gather the unique sensors for the legend
        if sensor not in sensors:
            sensors.append(sensor)

        # Collect all for a specific sensor
        # Sorted only works because we have date first in the list
        for (date, min_value, max_value, mean,
             stddev) in sorted(sensor_dict[sensor]):
            dates.append(date)
            min_values = np.append(min_values, min_value)
            max_values = np.append(max_values, max_value)
            mean_values = np.append(mean_values, mean)
            stddev_values = np.append(stddev_values, stddev)

        # These operate on and come out as numpy arrays
        min_values = scale_data_to_range(data_max, data_min,
                                         scale_max, scale_min, min_values)
        max_values = scale_data_to_range(data_max, data_min,
                                         scale_max, scale_min, max_values)
        mean_values = scale_data_to_range(data_max, data_min,
                                          scale_max, scale_min, mean_values)
        stddev_values = scale_data_to_range(data_max, data_min,
                                            scale_max, scale_min,
                                            stddev_values)

        # Draw the min to max line for these dates
        if plot_type == "Range":
            min_plot.vlines(dates, min_values, max_values,
                            colors=SENSOR_COLORS[sensor],
                            linestyles='solid', linewidths=1)

        # Plot the lists of dates and values for the subject
        values = list()
        if lower_subject == 'minimum':
            values = min_values
        if lower_subject == 'maximum':
            values = max_values
        if lower_subject == 'mean':
            values = mean_values
        if lower_subject == 'stddev':
            values = stddev_values

        # Draw the marker for these dates
        min_plot.plot(dates, values, marker=MARKER,
                      color=SENSOR_COLORS[sensor], linestyle='-',
                      markersize=float(MARKER_SIZE), label=sensor)
    # END - for sensor

    # ------------------------------------------------------------------------
    # Adjust the y range to help move them from the edge of the plot
    plot_y_min = display_min - 0.025
    plot_y_max = display_max + 0.025

    # Adjust the day range to help move them from the edge of the plot
    date_diff = plot_date_max - plot_date_min
    logger.debug(date_diff.days)
    for increment in range(0, int(date_diff.days/365) + 1):
        # Add 5 days to each end of the range for each year
        # With a minimum of 5 days added to each end of the range
        plot_date_min -= TIME_DELTA_5_DAYS
        plot_date_max += TIME_DELTA_5_DAYS
    logger.debug(plot_date_min)
    logger.debug(plot_date_max)

    # X Axis details
    min_plot.xaxis.set_major_locator(auto_date_locator)
    min_plot.xaxis.set_major_formatter(auto_date_formatter)
    min_plot.xaxis.set_minor_locator(auto_date_locator)

    # X Axis - Limits - Determine the date range of the to-be-displayed data
    min_plot.set_xlim(plot_date_min, plot_date_max)

    # X Axis - Label - Will always be 'Date'
    mpl_plot.xlabel('Date')

    # Y Axis details
    major_locator = MaxNLocator(max_n_locators)
    min_plot.yaxis.set_major_locator(major_locator)

    # Y Axis - Limits
    min_plot.set_ylim(plot_y_min, plot_y_max)

    # Y Axis - Label
    # We are going to make the Y Axis Label the title for now (See Title)
    # mpl_plot.ylabel(' '.join(subjects))

    # Plot - Title
    plot_name = ' '.join([plot_name, '-'] + subjects)
    # mpl_plot.title(plot_name)
    # The Title gets covered up by the legend so use the Y Axis Label
    mpl_plot.ylabel(plot_name)

    # Configure the legend
    legend = mpl_plot.legend(sensors,
                             bbox_to_anchor=(0.0, 1.01, 1.0, 0.5),
                             loc=3, ncol=5, mode="expand", borderaxespad=0.0,
                             numpoints=1, prop={'size': 12})

    # Change the legend background color to match the plot background color
    frame = legend.get_frame()
    frame.set_facecolor(BG_COLOR)

    # Fix the filename and save the plot
    filename = plot_name.replace('- ', '').lower()
    filename = filename.replace(' ', '_')
    filename = ''.join([filename, '_plot'])

    # Adjust the margins to be a little better
    mpl_plot.subplots_adjust(left=0.1, right=0.92, top=0.9, bottom=0.1)

    mpl_plot.grid(which='both', axis='y', linestyle='-')

    # Save the plot to a file
    mpl_plot.savefig('%s.png' % filename, dpi=100)

    # Close the plot so we can open another one
    mpl_plot.close()
# END - generate_plot


# ============================================================================
def generate_plots(plot_name, stat_files, band_type):
    '''
    Description:
      Gather all the information needed for plotting from the files and
      generate a plot for each statistic
    '''

    logger = logging.getLogger(__name__)

    stats = dict()

    # Read each file into a dictionary
    for stat_file in stat_files:
        logger.debug(stat_file)
        stats[stat_file] = \
            dict((key, value) for(key, value) in read_stats(stat_file))

    plot_subjects = ['Minimum', 'Maximum', 'Mean']
    generate_plot(plot_name, plot_subjects, band_type, stats, "Range")

    plot_subjects = ['Minimum']
    generate_plot(plot_name, plot_subjects, band_type, stats)

    plot_subjects = ['Maximum']
    generate_plot(plot_name, plot_subjects, band_type, stats)

    plot_subjects = ['Mean']
    generate_plot(plot_name, plot_subjects, band_type, stats)

    plot_subjects = ['StdDev']
    generate_plot(plot_name, plot_subjects, band_type, stats)
# END - generate_plots


# ============================================================================
def process_band_type(sensor_info, band_type):
    '''
    Description:
      A generic processing routine which finds the files to process based on
      the provided search criteria.  Utilizes the provided band type as part
      of the plot names and filenames.  If no files are found, no plots or
      combined statistics will be generated.
    '''

    single_sensor_files = list()
    multi_sensor_files = list()
    single_sensor_name = ''
    sensor_count = 0  # How many sensors were found....
    for (search_string, sensor_name) in sensor_info:
        single_sensor_files = glob.glob(search_string)
        if single_sensor_files and single_sensor_files is not None:
            if len(single_sensor_files) > 0:
                sensor_count += 1  # We found another sensor
                single_sensor_name = sensor_name
                generate_sensor_stats("%s %s" % (sensor_name, band_type),
                                      single_sensor_files)
                multi_sensor_files.extend(single_sensor_files)

    # Cleanup the memory for this while we process the multi-sensor list
    del single_sensor_files

    # We always use the multi sensor variable here because it will only have
    # the single sensor in it, if that is the case
    if sensor_count > 1:
        generate_plots("Multi Sensor %s" % band_type,
                       multi_sensor_files, band_type)
    elif sensor_count == 1:
        generate_plots("%s %s" % (single_sensor_name, band_type),
                       multi_sensor_files, band_type)
    # Else do not plot

    # Remove the processed files
    if sensor_count > 0:
        for filename in multi_sensor_files:
            if os.path.exists(filename):
                os.unlink(filename)

    del multi_sensor_files
# END - process_band_type


##############################################################################
# Define the configuration for searching for files and some of the text for
# the plots and filenames.  Doing this greatly simplified the code. :)
# Should be real easy to add others. :)

L4_SATELLITE_NAME = 'Landsat 4'
L5_SATELLITE_NAME = 'Landsat 5'
L7_SATELLITE_NAME = 'Landsat 7'
TERRA_SATELLITE_NAME = 'Terra'
AQUA_SATELLITE_NAME = 'Aqua'

# ----------------------------------------------------------------------------
# Only MODIS SR band 5 files
SR_SWIR_MODIS_B5_SENSOR_INFO = \
    [('MOD*sur_refl*b05.stats', TERRA_SATELLITE_NAME),
     ('MYD*sur_refl*b05.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# MODIS SR band 6 maps to Landsat SR band 5
SR_SWIR1_SENSOR_INFO = [('LT4*_sr_band5.stats', L4_SATELLITE_NAME),
                        ('LT5*_sr_band5.stats', L5_SATELLITE_NAME),
                        ('LE7*_sr_band5.stats', L7_SATELLITE_NAME),
                        ('MOD*sur_refl*6.stats', TERRA_SATELLITE_NAME),
                        ('MYD*sur_refl*6.stats', AQUA_SATELLITE_NAME)]

# MODIS SR band 7 maps to Landsat SR band 7
SR_SWIR2_SENSOR_INFO = [('LT4*_sr_band7.stats', L4_SATELLITE_NAME),
                        ('LT5*_sr_band7.stats', L5_SATELLITE_NAME),
                        ('LE7*_sr_band7.stats', L7_SATELLITE_NAME),
                        ('MOD*sur_refl*7.stats', TERRA_SATELLITE_NAME),
                        ('MYD*sur_refl*7.stats', AQUA_SATELLITE_NAME)]

# MODIS SR band 3 maps to Landsat SR band 1
SR_BLUE_SENSOR_INFO = [('LT4*_sr_band1.stats', L4_SATELLITE_NAME),
                       ('LT5*_sr_band1.stats', L5_SATELLITE_NAME),
                       ('LE7*_sr_band1.stats', L7_SATELLITE_NAME),
                       ('MOD*sur_refl*3.stats', TERRA_SATELLITE_NAME),
                       ('MYD*sur_refl*3.stats', AQUA_SATELLITE_NAME)]

# MODIS SR band 4 maps to Landsat SR band 2
SR_GREEN_SENSOR_INFO = [('LT4*_sr_band2.stats', L4_SATELLITE_NAME),
                        ('LT5*_sr_band2.stats', L5_SATELLITE_NAME),
                        ('LE7*_sr_band2.stats', L7_SATELLITE_NAME),
                        ('MOD*sur_refl*4.stats', TERRA_SATELLITE_NAME),
                        ('MYD*sur_refl*4.stats', AQUA_SATELLITE_NAME)]

# MODIS SR band 1 maps to Landsat SR band 3
SR_RED_SENSOR_INFO = [('LT4*_sr_band3.stats', L4_SATELLITE_NAME),
                      ('LT5*_sr_band3.stats', L5_SATELLITE_NAME),
                      ('LE7*_sr_band3.stats', L7_SATELLITE_NAME),
                      ('MOD*sur_refl*1.stats', TERRA_SATELLITE_NAME),
                      ('MYD*sur_refl*1.stats', AQUA_SATELLITE_NAME)]

# MODIS SR band 2 maps to Landsat SR band 4
SR_NIR_SENSOR_INFO = [('LT4*_sr_band4.stats', L4_SATELLITE_NAME),
                      ('LT5*_sr_band4.stats', L5_SATELLITE_NAME),
                      ('LE7*_sr_band4.stats', L7_SATELLITE_NAME),
                      ('MOD*sur_refl*2.stats', TERRA_SATELLITE_NAME),
                      ('MYD*sur_refl*2.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat TOA band 6 files
TOA_THERMAL_SENSOR_INFO = [('LT4*_toa_band6.stats', L4_SATELLITE_NAME),
                           ('LT5*_toa_band6.stats', L5_SATELLITE_NAME),
                           ('LE7*_toa_band6.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Landsat TOA band 5
TOA_SWIR1_SENSOR_INFO = [('LT4*_toa_band5.stats', L4_SATELLITE_NAME),
                         ('LT5*_toa_band5.stats', L5_SATELLITE_NAME),
                         ('LE7*_toa_band5.stats', L7_SATELLITE_NAME)]

# Landsat TOA band 7
TOA_SWIR2_SENSOR_INFO = [('LT4*_toa_band7.stats', L4_SATELLITE_NAME),
                         ('LT5*_toa_band7.stats', L5_SATELLITE_NAME),
                         ('LE7*_toa_band7.stats', L7_SATELLITE_NAME)]

# Landsat TOA band 1
TOA_BLUE_SENSOR_INFO = [('LT4*_toa_band1.stats', L4_SATELLITE_NAME),
                        ('LT5*_toa_band1.stats', L5_SATELLITE_NAME),
                        ('LE7*_toa_band1.stats', L7_SATELLITE_NAME)]

# Landsat TOA band 2
TOA_GREEN_SENSOR_INFO = [('LT4*_toa_band2.stats', L4_SATELLITE_NAME),
                         ('LT5*_toa_band2.stats', L5_SATELLITE_NAME),
                         ('LE7*_toa_band2.stats', L7_SATELLITE_NAME)]

# Landsat TOA band 3
TOA_RED_SENSOR_INFO = [('LT4*_toa_band3.stats', L4_SATELLITE_NAME),
                       ('LT5*_toa_band3.stats', L5_SATELLITE_NAME),
                       ('LE7*_toa_band3.stats', L7_SATELLITE_NAME)]

# Landsat TOA band 4
TOA_NIR_SENSOR_INFO = [('LT4*_toa_band4.stats', L4_SATELLITE_NAME),
                       ('LT5*_toa_band4.stats', L5_SATELLITE_NAME),
                       ('LE7*_toa_band4.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only MODIS band 20 files
EMIS_20_SENSOR_INFO = [('MOD*Emis_20.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_20.stats', AQUA_SATELLITE_NAME)]

# Only MODIS band 22 files
EMIS_22_SENSOR_INFO = [('MOD*Emis_22.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_22.stats', AQUA_SATELLITE_NAME)]

# Only MODIS band 23 files
EMIS_23_SENSOR_INFO = [('MOD*Emis_23.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_23.stats', AQUA_SATELLITE_NAME)]

# Only MODIS band 29 files
EMIS_29_SENSOR_INFO = [('MOD*Emis_29.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_29.stats', AQUA_SATELLITE_NAME)]

# Only MODIS band 31 files
EMIS_31_SENSOR_INFO = [('MOD*Emis_31.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_31.stats', AQUA_SATELLITE_NAME)]

# Only MODIS band 32 files
EMIS_32_SENSOR_INFO = [('MOD*Emis_32.stats', TERRA_SATELLITE_NAME),
                       ('MYD*Emis_32.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only MODIS Day files
LST_DAY_SENSOR_INFO = [('MOD*LST_Day_*.stats', TERRA_SATELLITE_NAME),
                       ('MYD*LST_Day_*.stats', AQUA_SATELLITE_NAME)]

# Only MODIS Night files
LST_NIGHT_SENSOR_INFO = [('MOD*LST_Night_*.stats', TERRA_SATELLITE_NAME),
                         ('MYD*LST_Night_*.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# MODIS and Landsat files
NDVI_SENSOR_INFO = [('LT4*_sr_ndvi.stats', L4_SATELLITE_NAME),
                    ('LT5*_sr_ndvi.stats', L5_SATELLITE_NAME),
                    ('LE7*_sr_ndvi.stats', L7_SATELLITE_NAME),
                    ('MOD*_NDVI.stats', TERRA_SATELLITE_NAME),
                    ('MYD*_NDVI.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# MODIS and Landsat files
EVI_SENSOR_INFO = [('LT4*_sr_evi.stats', L4_SATELLITE_NAME),
                   ('LT5*_sr_evi.stats', L5_SATELLITE_NAME),
                   ('LE7*_sr_evi.stats', L7_SATELLITE_NAME),
                   ('MOD*_EVI.stats', TERRA_SATELLITE_NAME),
                   ('MYD*_EVI.stats', AQUA_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat SAVI files
SAVI_SENSOR_INFO = [('LT4*_sr_savi.stats', L4_SATELLITE_NAME),
                    ('LT5*_sr_savi.stats', L5_SATELLITE_NAME),
                    ('LE7*_sr_savi.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat MSAVI files
MSAVI_SENSOR_INFO = [('LT4*_sr_msavi.stats', L4_SATELLITE_NAME),
                     ('LT5*_sr_msavi.stats', L5_SATELLITE_NAME),
                     ('LE7*_sr_msavi.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat NBR files
NBR_SENSOR_INFO = [('LT4*_sr_nbr.stats', L4_SATELLITE_NAME),
                   ('LT5*_sr_nbr.stats', L5_SATELLITE_NAME),
                   ('LE7*_sr_nbr.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat NBR2 files
NBR2_SENSOR_INFO = [('LT4*_sr_nbr2.stats', L4_SATELLITE_NAME),
                    ('LT5*_sr_nbr2.stats', L5_SATELLITE_NAME),
                    ('LE7*_sr_nbr2.stats', L7_SATELLITE_NAME)]

# ----------------------------------------------------------------------------
# Only Landsat NDMI files
NDMI_SENSOR_INFO = [('LT4*_sr_ndmi.stats', L4_SATELLITE_NAME),
                    ('LT5*_sr_ndmi.stats', L5_SATELLITE_NAME),
                    ('LE7*_sr_ndmi.stats', L7_SATELLITE_NAME)]
##############################################################################


# ============================================================================
def process_stats():
    '''
    Description:
      Process the stat results to plots.  If any bands/files do not exist,
      plots will not be generated for them.
    '''

    # --------------------------------------------------------------------
    process_band_type(SR_BLUE_SENSOR_INFO, "SR Blue")
    process_band_type(SR_GREEN_SENSOR_INFO, "SR Green")
    process_band_type(SR_RED_SENSOR_INFO, "SR Red")
    process_band_type(SR_NIR_SENSOR_INFO, "SR NIR")
    process_band_type(SR_SWIR1_SENSOR_INFO, "SR SWIR1")
    process_band_type(SR_SWIR2_SENSOR_INFO, "SR SWIR2")

    # --------------------------------------------------------------------
    process_band_type(SR_SWIR_MODIS_B5_SENSOR_INFO, "SR SWIR B5")

    # --------------------------------------------------------------------
    process_band_type(TOA_THERMAL_SENSOR_INFO, "SR Thermal")

    # --------------------------------------------------------------------
    process_band_type(TOA_BLUE_SENSOR_INFO, "TOA Blue")
    process_band_type(TOA_GREEN_SENSOR_INFO, "TOA Green")
    process_band_type(TOA_RED_SENSOR_INFO, "TOA Red")
    process_band_type(TOA_NIR_SENSOR_INFO, "TOA NIR")
    process_band_type(TOA_SWIR1_SENSOR_INFO, "TOA SWIR1")
    process_band_type(TOA_SWIR2_SENSOR_INFO, "TOA SWIR2")

    # --------------------------------------------------------------------
    process_band_type(EMIS_20_SENSOR_INFO, "Emis Band 20")
    process_band_type(EMIS_22_SENSOR_INFO, "Emis Band 22")
    process_band_type(EMIS_23_SENSOR_INFO, "Emis Band 23")
    process_band_type(EMIS_29_SENSOR_INFO, "Emis Band 29")
    process_band_type(EMIS_31_SENSOR_INFO, "Emis Band 31")
    process_band_type(EMIS_32_SENSOR_INFO, "Emis Band 32")

    # --------------------------------------------------------------------
    process_band_type(LST_DAY_SENSOR_INFO, "LST Day")
    process_band_type(LST_NIGHT_SENSOR_INFO, "LST Night")

    # --------------------------------------------------------------------
    process_band_type(NDVI_SENSOR_INFO, "NDVI")

    # --------------------------------------------------------------------
    process_band_type(EVI_SENSOR_INFO, "EVI")

    # --------------------------------------------------------------------
    process_band_type(SAVI_SENSOR_INFO, "SAVI")

    # --------------------------------------------------------------------
    process_band_type(MSAVI_SENSOR_INFO, "MSAVI")

    # --------------------------------------------------------------------
    process_band_type(NBR_SENSOR_INFO, "NBR")

    # --------------------------------------------------------------------
    process_band_type(NBR2_SENSOR_INFO, "NBR2")

    # --------------------------------------------------------------------
    process_band_type(NDMI_SENSOR_INFO, "NDMI")

# END - process_stats


# ============================================================================
def process(args):
    '''
    Description:
      Retrieves the stats directory from the specified location.
      Calls process_stats to generate the plots and combined stats files.
    '''

    global SENSOR_COLORS, BG_COLOR, MARKER, MARKER_SIZE

    logger = logging.getLogger(__name__)

    # Override the colors if they were specified
    SENSOR_COLORS['Terra'] = args.terra_color
    SENSOR_COLORS['Aqua'] = args.aqua_color
    SENSOR_COLORS['LT4'] = args.lt4_color
    SENSOR_COLORS['LT5'] = args.lt5_color
    SENSOR_COLORS['LE7'] = args.le7_color
    BG_COLOR = args.bg_color

    # Override the marker if they were specified
    MARKER = args.marker
    MARKER_SIZE = args.marker_size

    local_work_directory = 'lpcs_statistics'
    remote_stats_directory = os.path.join(args.order_directory, 'stats')
    remote_location = ''.join([args.source_host, ':', remote_stats_directory])

    # Make sure the directory does not exist
    shutil.rmtree(local_work_directory, ignore_errors=True)

    cmd = ' '.join(['scp', '-q', '-o', 'StrictHostKeyChecking=no',
                    '-c', 'arcfour', '-C', '-r', remote_location,
                    local_work_directory])
    try:
        output = execute_cmd(cmd)
    except Exception, e:
        if len(output) > 0:
            logger.info(output)
        logger.error("Failed retrieving stats from online cache")
        raise

    # Change to the statistics directory
    current_directory = os.getcwd()
    os.chdir(local_work_directory)

    try:
        process_stats()

        # Distribute back to the online cache
        lpcs_files = '*'
        remote_lpcs_directory = '%s/%s' % (args.order_directory,
                                           local_work_directory)
        logger.info("Creating lpcs_statistics directory %s on %s"
                    % (remote_lpcs_directory, args.source_host))
        cmd = ' '.join(['ssh', '-q', '-o', 'StrictHostKeyChecking=no',
                        args.source_host,
                        'mkdir', '-p', remote_lpcs_directory])
        output = ''
        try:
            output = execute_cmd(cmd)
        except Exception, e:
            if len(output) > 0:
                logger.error(output)
            raise

        # Transfer the lpcs plot and statistic files
        scp_transfer_file('localhost', lpcs_files, args.source_host,
                          remote_lpcs_directory)

        logger.info("Verifying statistics transfers")
        # NOTE - Re-purposing the lpcs_files variable
        lpcs_files = glob.glob(lpcs_files)
        for lpcs_file in lpcs_files:
            local_cksum_value = 'a b c'
            remote_cksum_value = 'b c d'

            # Generate a local checksum value
            cmd = ' '.join(['cksum', lpcs_file])
            try:
                local_cksum_value = execute_cmd(cmd)
            except Exception, e:
                if len(local_cksum_value) > 0:
                    logger.error(local_cksum_value)
                raise

            # Generate a remote checksum value
            remote_file = os.path.join(remote_lpcs_directory, lpcs_file)
            cmd = ' '.join(['ssh', '-q', '-o', 'StrictHostKeyChecking=no',
                            args.source_host, 'cksum', remote_file])
            try:
                remote_cksum_value = execute_cmd(cmd)
            except Exception, e:
                if len(remote_cksum_value) > 0:
                    logger.error(remote_cksum_value)
                raise

            # Checksum validation
            if local_cksum_value.split()[0] != remote_cksum_value.split()[0]:
                raise Exception(
                    "Failed checksum validation between %s and %s:%s"
                    % (lpcs_file, args.source_host, remote_file))
    finally:
        # Change back to the previous directory
        os.chdir(current_directory)
        # Remove the local_work_directory
        if not args.keep:
            shutil.rmtree(local_work_directory)

    logger.info("Plot Processing Complete")
# END - process


# ============================================================================
if __name__ == '__main__':
    '''
    Description:
      Grab the command line options, setup the logging and call the main
      process routine.
    '''

    # Build the command line argument parser
    parser = build_argument_parser()

    # Parse the command line arguments
    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    # TODO TODO TODO - need to specify a file ????
    logging.basicConfig(format=('%(asctime)s.%(msecs)03d %(process)d'
                                ' %(levelname)-8s'
                                ' %(filename)s:%(lineno)d:'
                                '%(funcName)s -- %(message)s'),
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=log_level)

    logger = logging.getLogger(__name__)

    try:
        # Process the specified order
        process(args)
    except Exception, e:
        if hasattr(e, 'output'):
            logger.error("Output [%s]" % e.output)
        logger.exception("Processing failed")
        sys.exit(EXIT_FAILURE)

    sys.exit(EXIT_SUCCESS)
