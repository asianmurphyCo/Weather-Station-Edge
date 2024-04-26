import mysql.connector
import pymongo
import time
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
from config import mqtt_host, mqtt_port, mqtt_topic, mongodb_host, mongodb_dbname, mysql_host, mysql_user, mysql_password, mysql_database

def check_and_reset_table():
    db_connection = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )
    cursor = db_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM weather_data")
    result = cursor.fetchone()

    if result[0] == 0:
        cursor.execute("ALTER TABLE weather_data AUTO_INCREMENT = 1")
        db_connection.commit()
        print("Table is empty. Reset recordID to 1.")
    else:
        print("Table is not empty.")

    cursor.close()
    db_connection.close()

check_and_reset_table()

def is_internet_connected():
    return True

def is_duplicate_document(document):
    myclient = pymongo.MongoClient(mongodb_host)
    mydb = myclient[mongodb_dbname]
    mycol = mydb["WeatherStation"]
    existing_doc = mycol.find_one({"recordTime": document["recordTime"]})
    myclient.close()
    return existing_doc is not None

def push_table_to_mongodb():
    db_connection = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )
    mycursor = db_connection.cursor(dictionary=True)
    mycursor.execute("SELECT * FROM weather_data")
    rows = mycursor.fetchall()

    myclient = pymongo.MongoClient(mongodb_host)
    mydb = myclient[mongodb_dbname]
    mycol = mydb["WeatherStation"]

    for row in rows:
        document = {
            "RecordID": row["recordID"],
            "recordDate": row["recordDate"].strftime('%Y-%m-%d'),
            "recordTime": str(row["recordTime"]),
            "temp": row["temp"],
            "humidity": row["humidity"],
            "baroPressure": row["baroPressure"],
            "windDirect": row["windDirect"],
            "avgWindSpd": row["avgWindSpd"],
            "mxWindSpd": row["mxWindSpd"],
            "rainPerHr": row["rainPerHr"],
            "rainPerDay": row["rainPerDay"]
        }

        if not is_duplicate_document(document):
            mycol.insert_one(document)
            print("Document inserted into MongoDB.")
        else:
            print("Duplicate document. Skipped insertion.")

    print("Table pushed to MongoDB.")
    mycursor.close()
    db_connection.close()
    myclient.close()

def on_message(client, userdata, msg):
    topic = msg.topic
    message = msg.payload.decode("utf-8")

    data = json.loads(message)
    temp = float(data["temperature"])
    humidity = float(data["humidity"])
    baroPressure = float(data["pressure"])
    windDirect = float(data["windDirection"])
    avgWindSpd = float(data["windSpeedAvg"])
    mxWindSpd = float(data["windSpeedMax"])
    rainPerHr = float(data["rainfall_H"])
    rainPerDay = float(data["rainfall_D"])

    db_connection = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )
    mycursor = db_connection.cursor(dictionary=True)

    insert_query = "INSERT INTO weather_data (temp, humidity, baroPressure, windDirect, avgWindSpd, mxWindSpd, rainPerHr, rainPerDay) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    insert_values = (temp, humidity, baroPressure, windDirect, avgWindSpd, mxWindSpd, rainPerHr, rainPerDay)
    mycursor.execute(insert_query, insert_values)
    db_connection.commit()

    document = {
        "recordID": mycursor.lastrowid,
        "recordDate": time.strftime('%Y-%m-%d'),
        "recordTime": time.strftime('%H:%M:%S'),
        "temp": temp,
        "humidity": humidity,
        "baroPressure": baroPressure,
        "windDirect": windDirect,
        "avgWindSpd": avgWindSpd,
        "mxWindSpd": mxWindSpd,
        "rainPerHr": rainPerHr,
        "rainPerDay": rainPerDay
    }

    myclient = pymongo.MongoClient(mongodb_host)
    mydb = myclient[mongodb_dbname]
    mycol = mydb["WeatherStation"]

    if not is_duplicate_document(document):
        mycol.insert_one(document)
        print("Message inserted into MySQL and MongoDB.")
    else:
        print("Duplicate document. Skipped insertion.")

    mycursor.close()
    db_connection.close()
    myclient.close()

client = mqtt.Client(CallbackAPIVersion.VERSION2)
client.on_message = on_message

client.connect(mqtt_host, mqtt_port)

client.subscribe(mqtt_topic)

if is_internet_connected():
    push_table_to_mongodb()

while True:
    client.loop()
    time.sleep(5)