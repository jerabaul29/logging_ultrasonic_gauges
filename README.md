# Logging_ultrasonic_gauges

This repository contains code that was used to log Banner ultrasonic gauges (S18UUAQ) in a series of experiments performed at the HSVA wave tank. The general architecture of the logging system is the following:

- Gauges are connected to the ADC channels of an Arduino Mega used as a logger. Here we logged 4 gauges per Mega, but 1 to 15 signals could be logged.
- One or several Arduino Mega are connected through USB to a computer, which reads, display and save the data collected in real time.
- To distinguish between the loggers, each one of them has a unique ID that is written in EEPROM and transmitted alongside data.

The corresponding code could be used for logging any 1 to 15 analog signals using an Arduino Mega, and while we used it for logging ultrasonic gauges, it could be used for any real time analog voltage logging.

Note that the system is not optimized for high logging speeds, as a logging frequency of 200Hz is more than enough for the purpose for which it was used.

## Hardware

At HSVA, 4 arrays of 4 gauges were each connected to a logging box based on an Arduino Mega. Each logging box connects the 4 gauges (outputting an analog signal from 0 to 10V) to the 4 first ADC channels of the arduino Mega (A0, A1, A2, A3) through a voltage divider of coefficient 0.5 (to convert the 0 to 10V gauges output into a 0 to 5V corresonding to the Mega range).

In addition, a trigger signal was wired into the box through channel A15.

## Preparation of the loggers

- Before using the loggers, make sure that their IDs are set and unique. To set the ID of an Arduino Mega, use the code in the *set_logger_ID* folder.
- Once the ID has been set on an Arduino Mega, upload the Arduino sketch *log_gauges/log_gauges.ino*. If necessary, adapt the #define parameters and the logical conditions for the trigger signal.
- Connect the analog voltages to log, the trigger signal, and the computer.

## Preparation of the logging computer

The logging computer should run Python 2.7 with several usual packages such as numpy and matplotlib.

## Logging and data export

- Make the computer ready for logging by using the *log_gauges/log_gauges.py* code. You may need to adapt paths. Make sure that all logger boxes are well discovered.
- Once the computer is ready, the output from the Mega will be logged once a trigger signal is received.
- Data is displayed in real time and saved in a *.logdata* file, which is really just a CSV file. The filename indicates UTC time at which you made the computer ready. UTC time of start and end of logging are contained in the .logdata file.
- Once the stop trigger signal is received, logging will stop automatically.
- You can convert the *.logdata* file into a Python *.pkl* file using the *log_gauges/generate_python_dict_data.py* file. The *.pkl* file contains the data as a Python dictionary which makes later Python import easy.

An example of *.logdata* and *.pkl* files are included in the *example_data* folder.


