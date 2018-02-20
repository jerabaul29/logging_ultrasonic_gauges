#include <EEPROM.h>

static const int address_EEPROM_ID = 0;
byte EEPROM_ID = 4;

void setup() {
  delay(2000);

  EEPROM.write(address_EEPROM_ID, EEPROM_ID);

  delay(500);

  Serial.begin(2000000);
  Serial.println();
  Serial.print(F("New board ID: "));
  Serial.println(EEPROM.read(address_EEPROM_ID));
}

void loop() {
  

}
