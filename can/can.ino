#include <SPI.h>
#include <mcp2515.h>

struct can_frame canMsg;
MCP2515 mcp2515(10);


void setup() {
  Serial.begin(500000);
  
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setNormalMode();
}

void loop() {
  if (mcp2515.readMessage(&canMsg) == MCP2515::ERROR_OK) {
    byte b[] = {canMsg.can_id >> 8, canMsg.can_id};
    Serial.write(b[0]); // ID1
    Serial.write(1);    // SEPARATOR
    Serial.write(b[1]); // ID2
    Serial.write(3);    // SEPARATOR
    Serial.write(canMsg.can_dlc);  // DLC
    Serial.write(5);    // SEPARATOR
    for (int i = 0; i < canMsg.can_dlc; i++) {
      Serial.write(canMsg.data[i]);   // DATA
      Serial.write(7+i*2);      // SEPARATOR
    }
    Serial.write("X");  // END BYTES
    Serial.write("X");  // END BYTES
  }
}
