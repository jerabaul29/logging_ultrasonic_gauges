from __future__ import division
from __future__ import print_function
import glob
import struct
import time
import serial
import numpy as np
from datetime import datetime
import os
from matplotlib import animation
import matplotlib.pyplot as plt

import multiprocessing

# // define all functions /////////////////////////////////////////////////////


def look_for_available_ports(verbose=0):
    """Find available serial ports that can potentially be Arduino cards.
    """
    available_ports = glob.glob('/dev/ttyACM*')
    if verbose > 0:
        print("Available porst: ")
        print(available_ports)

    return available_ports


def get_time_micros():
    return(int(round(time.time() * 1000000)))


def get_time_millis():
    return(int(round(time.time() * 1000)))


def get_time_seconds():
    return(int(round(time.time() * 1)))


def print_values(print_function, times, measurements, number, ID):
    """Print the logged values and timestamps obtained by the program from the
    Arduino logger."""
    print_function("")
    print_function("Logger ID: " + str(ID))
    print_function("Measurement number: " + str(number))
    for crrt_measurement, crrt_time in zip(measurements, times):
        print_function("%4i - uS %10i" % (crrt_measurement, crrt_time))


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


class ReadFromArduino(object):
    """A class to read the serial messages from Arduino."""

    def __init__(self, port, SIZE_STRUCT=29, verbose=0, print_color='ENDC', nbr_points_animate_plot=2000, filename=None, nbr_gauges=4, refresh_rate=0.050):
        self.port = port
        self.uS_last_measurement = get_time_micros()
        self.SIZE_STRUCT = SIZE_STRUCT
        self.verbose = verbose
        self.latest_values = ()
        self.t_reference = get_time_micros()
        self.time_since_start_logging_uS = 0
        self.time_elapsed_uS = 0
        self.logged_data = []
        self.utc_time_start = 0
        self.utc_time_finish = 0
        self.print_color = print_color
        self.read_and_plot_status = -1
        self.current_logged_data = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
        self.nbr_points_animate_plot = nbr_points_animate_plot
        self.filename = filename
        self.crrt_file = None
        self.nbr_gauges = nbr_gauges
        self.fig = None
        self.ax = None
        self.mode_interactive_plot = None
        self.refresh_rate = refresh_rate
        self.latest_measurement_utc = None

        self.port.flushInput()

    def read_next(self):
        """Read the next serial message from the Arduino: eiter wait, or a full
        data structure. Return a flag about which kind of result was obtained."""

        myByte = self.port.read(1)

        def print_in_color(string_in):
            bcolor_print(string_in, self.print_color)

        if myByte == 'S':  # start of a struct packet

            data = self.port.read(self.SIZE_STRUCT)  # read a whole structure in length
            myByte = self.port.read(1)

            if myByte == 'E':  # check if it actually were a struct packet

                current_time_uS = get_time_micros()
                self.time_since_start_logging_uS = (current_time_uS - self.t_reference)
                self.time_elapsed_uS = current_time_uS - self.uS_last_measurement
                self.uS_last_measurement = current_time_uS

                # is  a valid message struct: unpack the data
                self.latest_values = list(struct.unpack('<IIIIhhhhIB', data))

                if self.verbose > 1:
                    print("Python time elapsed since start logging (uS): " + str(self.time_since_start_logging_uS))
                    print("Python time elapsed since start logging (S): " + str(int(round(self.time_since_start_logging_uS) / 1000000)))
                    print("Python time elapsed since last logging (uS): " + str(self.time_elapsed_uS))

                if self.verbose > 0:
                    print_values(print_in_color, self.latest_values[0:4], self.latest_values[4:8], self.latest_values[8], self.latest_values[9])

                return('V')  # valid flag

            else:
                return('E')  # error: got the beginning of a struct, but not the end of it

        elif myByte == 'W':
            return('W')  # wait flag

        else:
            return('M')  # missaligned

        return('T')  # no input flag

    def read_continuously(self, timeout_S=None):
        """Log continuously, with serial plotting on terminal but no plotting."""

        if self.verbose > 0:
            bcolor_print("start read_continuously")
        continue_logging = True
        logging = False
        self.logged_data = []
        time_start = get_time_seconds()

        while continue_logging:
            return_flag = self.read_next()

            # take care of error flags
            if return_flag == 'E':
                bcolor_print("received flag E: error, found a Start but no End of struct")
                pass

            elif return_flag == 'M':
                pass
                # bcolor_print("received flag M: missaligned input")

            elif return_flag == 'T':
                bcolor_print("received flag T: serial read timeout")
                pass

            # take care of normal program execution
            if logging is False and return_flag == 'V':
                logging = True
                self.utc_time_start = datetime.utcnow()
                self.logged_data.append(self.latest_values)
                bcolor_print("start logging")

            elif logging and return_flag == 'V':
                self.logged_data.append(self.latest_values)

            elif logging and return_flag == 'W':
                logging = False
                self.utc_time_finish = datetime.utcnow()
                continue_logging = False
                bcolor_print("done logging")

            # take care of function timeout
            if timeout_S is not None:
                if (get_time_seconds() - time_start) > timeout_S:
                    bcolor_print("read_continuously timeout: stop logging")
                    continue_logging = False

    def read_and_plot(self, timeout_S=None):
        """Log all messages to be processed, until near exhaustion of serial port
        data, and prepare the data for real-time plotting."""

        if self.read_and_plot_status < 0:
            self.read_and_plot_status += 1

        if self.verbose > 0:
            bcolor_print("start read_and_plot: current status " + str(self.read_and_plot_status))
        continue_logging = True

        logging = False
        if self.read_and_plot_status == 1:
            logging = True

        while continue_logging and self.port.in_waiting > self.SIZE_STRUCT + 2:  # +2 is to make sure we will have the S and E flags

            self.latest_measurement_utc = datetime.utcnow()

            # if necessary, pop out some of the data to plot to keep it at max self.nbr_points_animate_plot
            while len(self.current_logged_data) > self.nbr_points_animate_plot:
                self.current_logged_data.pop(0)

            return_flag = self.read_next()

            # take care of error flags
            if return_flag == 'E':
                bcolor_print("received flag E: error, found a Start but no End of struct")
                pass

            elif return_flag == 'M':
                pass
                # bcolor_print("received flag M: missaligned input")

            elif return_flag == 'T':
                bcolor_print("received flag T: serial read timeout")
                pass

            # take care of normal program execution
            if logging is False and return_flag == 'V':

                # update the logging and status flags
                logging = True
                self.read_and_plot_status = 1

                self.utc_time_start = datetime.utcnow()

                self.current_logged_data.append(self.latest_values)
                self.logged_data.append(self.latest_values)

                if self.crrt_file is not None:
                    self.crrt_file.write("Computer UTC timestamp start logging: ")
                    self.crrt_file.write(str(self.utc_time_start))
                    self.crrt_file.write('\n')

                    # generate the header
                    header = ""
                    for ind_gauge in range(self.nbr_gauges):
                        header += "Arduino time Gauge " + str(ind_gauge) + " (uS)"
                        header += " | "
                    for ind_gauge in range(self.nbr_gauges):
                        header += "Gauge " + str(ind_gauge) + " (raw ADC)"
                        header += " | "
                    header += "Measurement nbr"
                    header += " | "
                    header += "Logger ID\n"

                    self.crrt_file.write(header)
                    self.crrt_file.write(str(self.latest_values)[1:-1])
                    self.crrt_file.write('\n')

                bcolor_print("start logging")

            elif logging and return_flag == 'V':

                self.current_logged_data.append(self.latest_values)
                self.logged_data.append(self.latest_values)

                if self.crrt_file is not None:
                    self.crrt_file.write(str(self.latest_values)[1:-1])
                    self.crrt_file.write('\n')

            elif logging and return_flag == 'W':

                logging = False
                continue_logging = False
                self.read_and_plot_status = 2

                self.utc_time_finish = datetime.utcnow()

                if self.crrt_file is not None:
                    self.crrt_file.write("Computer UTC timestamp finished logging: ")
                    self.crrt_file.write(str(self.utc_time_finish))

                bcolor_print("done logging")

        # generate the frames data
        current_logged_data_as_numpy = np.array(self.current_logged_data)
        list_plots = []
        list_colors = ['k', 'b', 'g', 'r', 'c', 'm', 'y']
        for ind_gauge in range(self.nbr_gauges):
            crrt_color = list_colors[ind_gauge]
            if self.mode_interactive_plot == 'ANIMATE':
                self.fig.clear()
                list_plots.append(plt.plot(current_logged_data_as_numpy[:, ind_gauge + self.nbr_gauges], color=crrt_color, label='gauge ' + str(ind_gauge)))
            elif self.mode_interactive_plot == 'DRAW':
                list_plots.append((current_logged_data_as_numpy[:, ind_gauge + self.nbr_gauges], crrt_color, 'gauge ' + str(ind_gauge)))

        return(list_plots)

    def animate_logging(self):
        self.mode_interactive_plot = 'ANIMATE'

        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.set_xlim([0, self.nbr_points_animate_plot])
        self.ax.set_ylim([0, 1024])

        with open(self.filename, 'w') as self.crrt_file:

            anim = animation.FuncAnimation(
                self.fig,
                self.read_and_plot,
                blit=False,
                interval=self.refresh_rate * 1000)

            plt.show()

    def log_and_draw(self):
        self.mode_interactive_plot = 'DRAW'

        plt.ion()
        fig, ax = plt.subplots(1)
        ax.set_xlim([0, self.nbr_points_animate_plot])
        ax.set_ylim([0, 1024])

        averaged_fps = 3

        with open(self.filename, 'w') as self.crrt_file:
            while self.read_and_plot_status < 2:
                crrt_utc = datetime.utcnow()

                title_string = ""
                if self.read_and_plot_status > -1:
                    averaged_fps = 0.8 * averaged_fps + 0.2 * 1.0 / (crrt_utc - last_draw_utc).total_seconds()
                    title_string += str(averaged_fps)[0: 3]
                    title_string += " averaged fps"
                last_draw_utc = crrt_utc
                if self.read_and_plot_status > 0:
                    crrt_time_elapsed_S = (self.latest_measurement_utc - self.utc_time_start).total_seconds()
                    title_string += " | logging time "
                    title_string += str(crrt_time_elapsed_S)[0: -4]
                    title_string += " s"

                list_plots = self.read_and_plot()
                fig.clear()
                for crrt_plot in list_plots:
                    plt.plot(crrt_plot[0], color=crrt_plot[1], label=crrt_plot[2])
                    ax.set_xlim([0, self.nbr_points_animate_plot])
                    ax.set_ylim([0, 1024])
                plt.title(title_string)
                plt.legend(loc=2)
                plt.draw()
                plt.pause(self.refresh_rate)


class perform_several_loggings(object):
    """A class to perform several loggins simultaneously."""

    def __init__(self, baud_rate=2000000, verbose=0, mode_detect_usb_port='AUTOMATIC', nbr_gauges=4, path_to_save=None, case_name="logging_"):
        self.baud_rate = baud_rate
        self.dict_logging_instances = {}
        self.dict_threads = {}
        self.verbose = verbose
        self.dict_all_data = {}
        self.dict_utc_timestamps = {}
        self.mode_detect_usb_port = mode_detect_usb_port
        self.nbr_gauges = nbr_gauges
        self.path_to_save = path_to_save
        self.case_name = case_name
        self.list_filenames = []

        if self.path_to_save is None:
            self.path_to_save = os.getcwd()

        all_ports = look_for_available_ports()
        nbr_logging = 0

        utc_start_logging = datetime.utcnow()
        list_usb_ports = []

        if mode_detect_usb_port == 'SELECT_PORT':
            for crrt_port in all_ports:

                print("Showing the output of port: " + crrt_port + " at baud rate " + str(self.baud_rate))
                print("-----------------------------")

                usb_port = serial.Serial(crrt_port, baudrate=baud_rate, timeout=0.1)
                usb_port.flushInput()

                for i in range(5):
                    crrt_char = usb_port.read()
                    print(crrt_char)

                print("-----------------------------")

                print("Log this port? [y]es, [n]o")

                wait_for_answer = True
                while wait_for_answer:
                    answer = raw_input()
                    if answer == 'y':
                        list_usb_ports.append((usb_port, crrt_port))
                        wait_for_answer = False
                    elif answer == 'n':
                        wait_for_answer = False
                    else:
                        print("[y]es or [n]o")

        # idea here: catch the 'W' wait flags, this is specific to the loggers
        elif mode_detect_usb_port == 'AUTOMATIC':
            for crrt_port in all_ports:

                usb_port = serial.Serial(crrt_port, baudrate=baud_rate, timeout=0.1)
                usb_port.flushInput()

                for i in range(5):
                    crrt_char = usb_port.read()
                    if crrt_char == 'W':
                        print("Adding " + crrt_port + " to list ports to use")
                        list_usb_ports.append((usb_port, crrt_port))
                        break

        else:
            print("mode_detect_usb_port " + self.mode_detect_usb_port + " is not implemented!")

        for crrt_usb_port in list_usb_ports:

            # determine the filename to use
            filename_crrt = self.path_to_save + "/" + case_name + str(utc_start_logging) + "_" + str(nbr_logging)
            filename_crrt = filename_crrt.replace(" ", "_")
            filename_crrt = filename_crrt.replace(".", "")
            filename_crrt += ".logdat"
            print("Using filename: " + filename_crrt)
            self.list_filenames.append(filename_crrt)

            self.dict_logging_instances[crrt_usb_port[1]] = ReadFromArduino(crrt_usb_port[0], verbose=self.verbose,
                                                                            print_color=list_colors[nbr_logging],
                                                                            filename=filename_crrt, nbr_gauges=self.nbr_gauges)
            nbr_logging += 1

    def perform_logging(self, mode='DRAW'):
        print("create all logging instances")
        for crrt_logging in self.dict_logging_instances:
            if mode == 'ANIMATE':
                crrt_thread = multiprocessing.Process(target=self.dict_logging_instances[crrt_logging].animate_logging)
            elif mode == 'MINIMAL':
                crrt_thread = multiprocessing.Process(target=self.dict_logging_instances[crrt_logging].read_continuously)
            elif mode == 'DRAW':
                crrt_thread = multiprocessing.Process(target=self.dict_logging_instances[crrt_logging].log_and_draw)
            else:
                print("mode " + mode + " in perform_several_loggings.perform_logging not implemented")
            self.dict_threads[crrt_logging] = crrt_thread

        print("start all threads")
        for crrt_thread in self.dict_threads:
            self.dict_threads[crrt_thread].start()

        for crrt_thread in self.dict_threads:
            self.dict_threads[crrt_thread].join()
        print("joined all threads")

    def return_filenames(self):
        return(self.list_filenames)


# // use the code //////////////////////////////////////////////////////////////
instance_perform_all_logging = perform_several_loggings(verbose=0, path_to_save='/home/jrlab/Desktop/Data/DataHSVA/')
instance_perform_all_logging.perform_logging()
list_loggedd_filenames = instance_perform_all_logging.return_filenames()
