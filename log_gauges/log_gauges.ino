/*

NOTE / TODO:

The pooling on ADC A15 for checking if should start to log is slow and inefficient, but OK for the
kind of applications considered. Using an interrup pin would be a better solution if anything should
be done at high speed.

*/

#include <EEPROM.h>
#include <avr/wdt.h>

// control of the synchronization signal ////////////////////////////////////////////////////////
#define PIN_SYNC A15
#define threshold_sync 364
#define WAIT_FOR_TRIGGER true  // wait for trigger signal or start logging at once
#define DELAY_BEFORE_NEXT_MEASUREMENT_MS 60000  // minimum delay between end of a measurement and the next measurement
#define REQUIRED_NBR_TRIGGER_MEASUREMENTS 10  // this is because sometimes spikes on the trigger signal: make sure trigger and not spike
#define MS_TIME_BETWEEN_TRIGGER_MEASUREMENTS 5  // to make sure we are not measuring a small duration spike

boolean logging = false;
int value_synchronization = 0;

// if should use human or binary serial transmission ////////////////////////////////////////////
#define HUMAN_OUTPUT false

// ID of the logger /////////////////////////////////////////////////////////////////////////////
static const int address_EEPROM_ID = 0;
byte EEPROM_ID;

// technical delays /////////////////////////////////////////////////////////////////////////////
#define DELAY_TRANSMIT_uS 0
#define DELAY_MEASUREMENT_uS 0

// about frequency and timing of the measurements ///////////////////////////////////////////////

// measurement frequency is set here
#define MEASUREMENT_FREQUENCY_HZ 200.0
#define MIN_DURATION_LOGGING_mS 800000  // minimum duration of the logging: will not look for stop trigger before this value has elpased

#define S_to_uS 1000000.0
static const unsigned long interval_measurements_uS = S_to_uS / MEASUREMENT_FREQUENCY_HZ;

unsigned long time_last_measurements_uS;
unsigned long start_measurement_time = 0;
unsigned long start_measurement_time_mS = 0;

// about the measurements to perform ////////////////////////////////////////////////////////////

#define NBR_PINS_TO_MEASURE 4  // how many input channels

// define constants for the maximum theoretical number of input channels on Arduino Mega
static const uint8_t analog_pins[] = {A0,  A1,  A2,  A3,  A4,  A5,  A6,  A7,  A8 };
static const char    symbol_pins[] = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'};

// the struct to transmit the measurements to the computer
struct gauges_data {
  unsigned long reading_times[NBR_PINS_TO_MEASURE];
  int reading_values[NBR_PINS_TO_MEASURE];
  unsigned long measurement_nbr = 0;
  byte logger_ID = 255;
};

gauges_data gauges_data_instance;

static const int len_gauges_data_instance = sizeof(gauges_data_instance);

// start of the code ///////////////////////////////////////////////////////////////////////////

void setup() {

  delay(0);

  Serial.begin(2000000);

  EEPROM_ID = EEPROM.read(address_EEPROM_ID);
  gauges_data_instance.logger_ID = EEPROM_ID;

  // print_information();  // to use if need to check information about the struct being sent

  time_last_measurements_uS = micros();

}

void loop() {

  // need to wait for trigger --------------------------------------------------
  #if WAIT_FOR_TRIGGER
  if (!logging) {
    value_synchronization = analogRead(PIN_SYNC);

    if (value_synchronization > threshold_sync) {

      if (received_trigger_signal()){
        logging = true;
        time_last_measurements_uS = micros();
        start_measurement_time = micros();
        start_measurement_time_mS = millis();
      }

    }

    else {
      Serial.print("W");
      delay(5);
    }
  }

  else {
    if (micros() - time_last_measurements_uS > interval_measurements_uS) {
      time_last_measurements_uS += interval_measurements_uS;

      update_all_measurements();

      #if HUMAN_OUTPUT
      send_all_measurements_human();
      #else
      send_all_measurements_binary();
      #endif
    }

    value_synchronization = analogRead(PIN_SYNC);

    // the second part of the condition is to avoid bad effects due to switches etc on the trigger signal
    if ((value_synchronization > threshold_sync) && (millis() - start_measurement_time_mS > MIN_DURATION_LOGGING_mS)) {

      if (received_trigger_signal()){
        logging = false;
        for (int i=0; i<500; i++){
          Serial.print("W");
          delay(5);
        }
        delay(DELAY_BEFORE_NEXT_MEASUREMENT_MS);
        wdt_enable(WDTO_15MS);
        wdt_reset();
        while (1){
          // wait for reboot
        }
      }
    }
  }

  // do not need to wait for trigger -------------------------------------------
  #else
  if (micros() - time_last_measurements_uS > interval_measurements_uS) {
    time_last_measurements_uS += interval_measurements_uS;

    update_all_measurements();

    #if HUMAN_OUTPUT
    send_all_measurements_human();
    #else
    send_all_measurements_binary();
    #endif
  }

}

void update_all_measurements() {
  for (int i = 0; i < NBR_PINS_TO_MEASURE; i++) {
    gauges_data_instance.reading_times[i] = micros() - start_measurement_time;
    gauges_data_instance.reading_values[i] = analogRead(analog_pins[i]);

    #if DELAY_MEASUREMENT_uS > 0
    delayMicroseconds(DELAY_MEASUREMENT_uS);
    #endif
  }

  gauges_data_instance.measurement_nbr += 1;
}

void send_all_measurements_human() {

  Serial.println();
  Serial.print("M");
  Serial.print(gauges_data_instance.measurement_nbr);
  Serial.println();

  for (int i = 0; i < NBR_PINS_TO_MEASURE; i++) {
    Serial.print(symbol_pins[i]);
    Serial.print(gauges_data_instance.reading_values[i]);
    delayMicroseconds(DELAY_TRANSMIT_uS);
    Serial.print(" ");
    Serial.print('u');
    Serial.print(gauges_data_instance.reading_times[i]);
    delayMicroseconds(DELAY_TRANSMIT_uS);
    Serial.println();
  }
}

void send_all_measurements_binary() {
  Serial.write('S');
  Serial.write((uint8_t *)&gauges_data_instance, len_gauges_data_instance);
  Serial.write('E');
}

void print_information() {
  Serial.println();
  Serial.println();
  Serial.print(F("Size structure: "));
  Serial.println(len_gauges_data_instance);
  Serial.print(F("Logger ID: "));
  Serial.println(EEPROM_ID);
  Serial.print(F("interval_measurements_uS: "));
  Serial.println(interval_measurements_uS);
  Serial.println();
  Serial.println();
}

bool received_trigger_signal(void){
  // a function to check if a trigger signal was received, based on several trigger poolings;
  // this is because at HSVA, there was sometimes noise on the trigger line.

  for (int i=0; i<REQUIRED_NBR_TRIGGER_MEASUREMENTS; i++){
    int current_trigger_value = analogRead(PIN_SYNC);

    if (current_trigger_value < threshold_sync){
      return(false);
    }

    delay(MS_TIME_BETWEEN_TRIGGER_MEASUREMENTS);
  }

  return(true);
}
