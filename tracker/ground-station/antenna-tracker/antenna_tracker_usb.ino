// ==========================
// Pin Definitions
// ==========================

#define AZ_IN1 14
#define AZ_IN2 27
#define AZ_IN3 26
#define AZ_IN4 25

#define EL_IN1 33
#define EL_IN2 32
#define EL_IN3 18
#define EL_IN4 19

// 28BYJ-48 Half-Step Sequence
const int stepSequence[8][4] = {
  {1,0,0,0},
  {1,1,0,0},
  {0,1,0,0},
  {0,1,1,0},
  {0,0,1,0},
  {0,0,1,1},
  {0,0,0,1},
  {1,0,0,1}
};

int azStepIndex = 0;
int elStepIndex = 0;

int stepDelay = 2;

void setMotor(int in1, int in2, int in3, int in4, int stepIndex) {
  digitalWrite(in1, stepSequence[stepIndex][0]);
  digitalWrite(in2, stepSequence[stepIndex][1]);
  digitalWrite(in3, stepSequence[stepIndex][2]);
  digitalWrite(in4, stepSequence[stepIndex][3]);
}

void stepMotor(bool azimuth, int direction) {

  if (azimuth) {
    azStepIndex += direction;
    if (azStepIndex > 7) azStepIndex = 0;
    if (azStepIndex < 0) azStepIndex = 7;
    setMotor(AZ_IN1, AZ_IN2, AZ_IN3, AZ_IN4, azStepIndex);
  } else {
    elStepIndex += direction;
    if (elStepIndex > 7) elStepIndex = 0;
    if (elStepIndex < 0) elStepIndex = 7;
    setMotor(EL_IN1, EL_IN2, EL_IN3, EL_IN4, elStepIndex);
  }

  delay(stepDelay);
}

void moveSteps(bool azimuth, int steps) {

  int direction = (steps > 0) ? 1 : -1;
  steps = abs(steps);

  for (int i = 0; i < steps; i++) {
    stepMotor(azimuth, direction);
  }
}

void setup() {

  Serial.begin(115200);

  pinMode(AZ_IN1, OUTPUT);
  pinMode(AZ_IN2, OUTPUT);
  pinMode(AZ_IN3, OUTPUT);
  pinMode(AZ_IN4, OUTPUT);

  pinMode(EL_IN1, OUTPUT);
  pinMode(EL_IN2, OUTPUT);
  pinMode(EL_IN3, OUTPUT);
  pinMode(EL_IN4, OUTPUT);

  Serial.println("Antenna Tracker Ready");
  Serial.println("Commands:");
  Serial.println("AZ <steps>");
  Serial.println("EL <steps>");
}

void loop() {

  if (Serial.available()) {

    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("AZ")) {
      int steps = command.substring(2).toInt();
      moveSteps(true, steps);
      Serial.println("AZ done");
    }

    else if (command.startsWith("EL")) {
      int steps = command.substring(2).toInt();
      moveSteps(false, steps);
      Serial.println("EL done");
    }

    else if (command == "STOP") {
      Serial.println("Stop not implemented yet");
    }
  }
}
