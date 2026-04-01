// #include <DHT.h>
// #include <DHT_U.h>

#include <TurtleBot3_ROS2.h> // 터틀봇 라이브러리 포함

//////////////////////////
// PIN CONFIG
//////////////////////////
// #define DHTPIN 4  
// #define DHTTYPE DHT11
// DHT dht(DHTPIN, DHTTYPE);

#define TRIG_PIN 2
#define ECHO_PIN 3
#define CDS1 A1
#define CDS2 A2
#define CDS3 A3
#define IR_PIN A0
#define GAS_PIN A4

//////////////////////////
// 타이머 변수 설정 (delay 대체)
//////////////////////////
unsigned long previousMillis = 0;
const long interval = 500; // 500ms(0.5초) 간격 전송

void setup()
{
  // 1. 라즈베리 파이 센서 통신용 (UART)
  Serial2.begin(57600); 
  
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(IR_PIN, INPUT);
  pinMode(GAS_PIN, INPUT);

  // dht.begin();
  
  // 2. 터틀봇 메인 시스템 활성화 (라즈베리파이 ROS 2 통신용)
  TurtleBot3Core::begin("Burger"); 
}

void loop()
{
  unsigned long currentMillis = millis();

  // 0.5초(500ms)가 지날 때마다 한 번씩만 센서를 읽고 전송 (OpenCR을 멈추지 않음!)
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    // 1. 센서 값 읽기
    int cds1 = analogRead(CDS1);
    int cds2 = analogRead(CDS2);
    int cds3 = analogRead(CDS3);
    // float humidity = dht.readHumidity();
    // float temperature = dht.readTemperature();

    digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    
    // pulseIn 타임아웃을 30000(30ms)으로 제한하여 시스템 지연 방지
    long duration = pulseIn(ECHO_PIN, HIGH, 30000);
    float distance = (duration > 0) ? (duration * 0.034 / 2.0) : 200.0;

    int ir_val = digitalRead(IR_PIN);
    int gas_val = analogRead(GAS_PIN);
    
    // 2. JSON 출력 (마지막 gas 콤마 제거 완료)
    Serial2.print("{");
    Serial2.print("\"cds1\":");     Serial2.print(cds1);        Serial2.print(",");
    Serial2.print("\"cds2\":");     Serial2.print(cds2);        Serial2.print(",");
    Serial2.print("\"cds3\":");     Serial2.print(cds3);        Serial2.print(",");
    // Serial2.print("\"temp\":");     Serial2.print(isnan(temperature) ? 0 : temperature); Serial2.print(",");
    // Serial2.print("\"hum\":");      Serial2.print(isnan(humidity) ? 0 : humidity);    Serial2.print(",");
    Serial2.print("\"distance\":"); Serial2.print(distance);    Serial2.print(",");
    Serial2.print("\"ir\":");       Serial2.print(ir_val);      Serial2.print(",");
    Serial2.print("\"gas\":");      Serial2.print(gas_val);
    Serial2.println("}");
  }

  // 3. 터틀봇 코어 통신 루프 (이 부분은 delay 없이 항상 초고속으로 돌아가야 합니다!)
  TurtleBot3Core::run();
}