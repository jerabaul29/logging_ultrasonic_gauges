from __future__ import print_function
import numpy as np
import pickle
import matplotlib.pyplot as plt
import os
import glob
from StringIO import StringIO

# list_colors should agree with the keys of bcolor_print function under
list_colors = ['OKBLUE', 'OKGREEN', 'WARNING', 'FAIL']


def bcolor_print(string_in, bcolor='WARNING'):
    """note: maybe this would be better with clearer color names. Color names are
    the keys of dict_colors."""

    dict_colors = {'HEADER': '\033[95m',
                   'OKBLUE': '\033[94m',
                   'OKGREEN': '\033[92m',
                   'WARNING': '\033[93m',
                   'FAIL': '\033[91m',
                   'ENDC': '\033[0m',
                   'BOLD': '\033[1m',
                   'UNDERLINE': '\033[4m'}

    print(dict_colors[bcolor] + string_in + dict_colors['ENDC'])


class LoggedDataConverter(object):
    def __init__(self, verbose=0, path_in=None, path_out=None, perform_quality_checks=True, show_all=True):
        self.verbose = verbose
        self.list_generated_pickles = []
        self.perform_quality_checks = perform_quality_checks
        self.show_all = show_all

        self.path_in = path_in
        if path_in is None:
            self.path_in = os.getcwd()
        self.path_in += "/"

        if self.verbose > 0:
            print("- using path_in: " + self.path_in)

        self.path_out = path_out
        if path_out is None:
            self.path_out = os.getcwd()
        self.path_out += "/"

        if self.verbose > 0:
            print("- using path_out: " + self.path_out)

    def find_data_files(self):
        regexp_string_datafiles = self.path_in + '*.logdat'

        if self.verbose > 4:
            print("using regexp_string_datafiles: " + regexp_string_datafiles)

        self.available_data_files = glob.glob(regexp_string_datafiles)

        if self.verbose > 0:
            print("- found data files:")
            for crrt_datafile in self.available_data_files:
                print(crrt_datafile)

    def generate_save_dict_one_datafile(self, datafile_path):
        if self.verbose > 0:
            print("- processing datafile: " + datafile_path)

        dict_datafile_data = {}

        crrt_basename = os.path.basename(datafile_path)[: -7]

        # read all data
        with open(datafile_path) as crrt_file:
            crrt_file_content = crrt_file.read()

        crrt_file_content = crrt_file_content[0: -1]  # -1 is to take care of end-of-file char introduced by some text editors

        # get timestamp start
        all_lines = crrt_file_content.split('\n')

        first_line = all_lines[0]
        timestamp_start = first_line[38:]
        dict_datafile_data["UTC_start"] = timestamp_start

        if self.verbose > 4:
            print(timestamp_start)

        # get timestamp end
        timestamp_end = all_lines[-1][41:]
        dict_datafile_data["UTC_end"] = timestamp_end

        if self.verbose > 4:
            print(timestamp_end)

        # get logged data
        lines_with_information = "\n".join(all_lines[2:-1])
        crrt_information_as_numpy = np.genfromtxt(StringIO(lines_with_information), delimiter=",")

        # get the different information parts
        logger_ID = crrt_information_as_numpy[0, 9]

        if self.verbose > 4:
            print("logger_ID: " + str(logger_ID))

        dict_datafile_data["logger_ID"] = logger_ID

        # get the numbers of the measurements
        measurement_numbers = crrt_information_as_numpy[:, 8]

        dict_datafile_data["measurement_numbers"] = measurement_numbers

        if self.verbose > 4:
            print("measurement_numbers number 100: " + str(measurement_numbers[99]))

        # check that no measurements are missing
        if self.perform_quality_checks:
            d_measurement_numbers = measurement_numbers[1:] - measurement_numbers[0:-1]
            missing_measurement = d_measurement_numbers > 1
            width_missing_measurements = list(d_measurement_numbers[missing_measurement] - 1)
            list_lines = np.where(missing_measurement)[0].tolist()
            nbr_missing_measurements = np.sum(missing_measurement)

            if nbr_missing_measurements > 0:
                bcolor_print("missing measurements at " + str(nbr_missing_measurements) + " places out of " + str(crrt_information_as_numpy.shape[0]))
                bcolor_print("this is " + str(100.0 * nbr_missing_measurements / crrt_information_as_numpy.shape[0]) + " percent")
                for (crrt_line, crrt_width) in zip(list_lines, width_missing_measurements):
                    bcolor_print("at line " + str(crrt_line) + " there are " + str(int(crrt_width)) + " missing measurements")

        # get the timestamps and data
        number_of_logged_signals = (crrt_information_as_numpy.shape[1] - 2) / 2

        if self.verbose > 4:
            print("number_of_logged_signals: " + str(number_of_logged_signals))

        dict_datafile_data["number_of_logged_signals"] = number_of_logged_signals

        for ind_signal in range(number_of_logged_signals):
            crrt_datastamps = crrt_information_as_numpy[:, ind_signal]
            crrt_data = crrt_information_as_numpy[:, number_of_logged_signals + ind_signal]
            dict_datafile_data["timestamps_signal_" + str(ind_signal)] = crrt_datastamps
            dict_datafile_data["data_signal_" + str(ind_signal)] = crrt_data

        name_pickle_out = self.path_out + crrt_basename + ".pkl"
        self.list_generated_pickles.append(name_pickle_out)

        if self.verbose > 0:
            print("- saving with pickle as: " + name_pickle_out)
            
        with open(name_pickle_out, 'wb') as handle:
            pickle.dump(dict_datafile_data, handle, protocol=pickle.HIGHEST_PROTOCOL)

        if self.show_all:
            self.show_pickled_data(len(self.list_generated_pickles) - 1)

    def generate_save_dict_one_folder(self):
        for crrt_datafile in self.available_data_files:
            self.generate_save_dict_one_datafile(crrt_datafile)

    def show_pickled_data(self, which_pickled=0):
        print("list of available pickle data:")
        for crrt_pickled in self.list_generated_pickles:
            print(crrt_pickled)
            
        print("showing: " + str(self.list_generated_pickles[which_pickled]))
    
        pickled_to_show = self.list_generated_pickles[which_pickled]

        with open(pickled_to_show, 'r') as handle:
            dict_read = pickle.load(handle)

        plt.figure()
        nbr_of_signals = dict_read["number_of_logged_signals"]
        for ind_signal in range(nbr_of_signals):
            plt.plot(dict_read["timestamps_signal_" + str(ind_signal)] / 1e6, dict_read["data_signal_" + str(ind_signal)], label="signal " + str(ind_signal))
        plt.xlabel("Arduino timestamps (s)")
        plt.ylabel("Raw data (10 bits ADC)")
        plt.title(os.path.basename(pickled_to_show))
        plt.ylim([0, 1024])
        plt.legend()
        plt.show()

# use the code /////////////////////////////////////////////////////////////////
instance_LoggedDataConverter = LoggedDataConverter(verbose=1, path_in='/home/jrlab/Desktop/Data/DataHSVA/', path_out='/home/jrlab/Desktop/Data/DataHSVA_pickled/')
instance_LoggedDataConverter.find_data_files()
instance_LoggedDataConverter.generate_save_dict_one_folder()
