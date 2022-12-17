import logging

from fastapi import FastAPI
from datetime import datetime
from databricks import sql
import os
import requests
from fastapi.middleware.cors import CORSMiddleware

SERVER_HOST: str = os.environ['SERVER_HOST']
HTTP_PATH: str = os.environ['HTTP_PATH']
ACCESS_TOKEN: str = os.environ['TOKEN']
NOTEBOOK_PATH: str = os.environ["NOTEBOOK_PATH"]
CLUSTER_ID: str = os.environ["CLUSTER_ID"]

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:8080"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def dbfs_rpc(action, body):
    """ A helper function to make the DBFS API request, request/response is encoded/decoded as JSON """
    response = requests.post(
        action,
        headers={'Authorization': 'Bearer %s' % ACCESS_TOKEN},
        json=body
    )
    return response.json()


def scheduler_parser(time, interval, repeats):
    hour, min = time.split(':')

    if interval == 'Every Hour':
        return f"0 {min} * * * ?"
    elif interval == 'Every Day':
        return f"0 {min} {hour} * * ?"
    elif interval == 'Every Month':
        return f"0 {min} {hour} 1 * ?"
    elif repeats['su'] or repeats['mo'] or repeats['tu'] or repeats['we'] or repeats['thu'] or repeats['fri'] or \
            repeats['sat']:
        days = [repeats['su'], repeats['mo'], repeats['tu'], repeats['we'], repeats['thu'], repeats['fri'],
                repeats['sat']]
        day_week_concat = ""
        for num_day, day in enumerate(days):
            if num_day == 0 and day:
                if day_week_concat == '':
                    day_week_concat += 'Sun'
                else:
                    day_week_concat += ',Sun'
            if num_day == 1 and day:
                if day_week_concat == '':
                    day_week_concat += 'Mon'
                else:
                    day_week_concat += ',Mon'
            if num_day == 2 and day:
                if day_week_concat == '':
                    day_week_concat += 'Tue'
                else:
                    day_week_concat += ',Tue'
            if num_day == 3 and day:
                if day_week_concat == '':
                    day_week_concat += 'Wed'
                else:
                    day_week_concat += ',Wed'
            if num_day == 4 and day:
                if day_week_concat == '':
                    day_week_concat += 'Thu'
                else:
                    day_week_concat += ',Thu'
            if num_day == 5 and day:
                if day_week_concat == '':
                    day_week_concat += 'Fri'
                else:
                    day_week_concat += ',Fri'
            if num_day == 6 and day:
                if day_week_concat == '':
                    day_week_concat += 'Sat'
                else:
                    day_week_concat += ',Sat'

        if day_week_concat != '':
            return f"0 {min} {hour} ? * {day_week_concat}"
    elif interval == 'Every Week':
        return f"0 {min} {hour} ? * Mon"
    else:
        return None






@app.get("/databases", tags=["Tables"])
async def get_databases() -> list:
    """
    Get the databases from Databricks
    """
    connection = sql.connect(
        server_hostname=SERVER_HOST,
        http_path=HTTP_PATH,
        access_token=ACCESS_TOKEN)

    cursor = connection.cursor()

    cursor.execute("SHOW DATABASES")
    dbs = cursor.fetchall()
    res = []
    for db in dbs:
        res.extend(db)

    cursor.close()
    connection.close()
    return res


@app.post("/tables", tags=["tables"])
async def get_tables(db: dict) -> list:
    """
        Get Tables from db
    """

    connection = sql.connect(
        server_hostname=SERVER_HOST,
        http_path=HTTP_PATH,
        access_token=ACCESS_TOKEN)

    cursor = connection.cursor()

    cursor.execute(f"SHOW TABLES IN {db['db']}")

    tables = cursor.fetchall()
    cursor.close()
    connection.close()
    return [tbl[1] for tbl in tables]


@app.post("/columns", tags=["columns"])
async def get_columns(schema: dict):
    """
        Get columns from the table
    """

    connection = sql.connect(
        server_hostname=SERVER_HOST,
        http_path=HTTP_PATH,
        access_token=ACCESS_TOKEN
    )

    cursor = connection.cursor()

    cursor.execute(f"SHOW COLUMNS IN {schema['db']}.{schema['table']}")

    columns = cursor.fetchall()
    res = []
    for col in columns:
        res.extend(col)

    cursor.close()
    connection.close()
    return res



@app.post("/send_checker", tags=["send_job_info"])
async def send_checker(info: dict):
    """
       Send parameter for checker
    """

    checker_name: str = info["checkerName"]
    db_name: str = info["db"]
    table_name: str = info["table"]
    checkers: str = str(info["checker"])
    filtration_condition = info["filtrationCondition"]
    time: str = info["time"]
    interval: str = info["interval"]
    repeats: str = eval(str(info["repeats"]))
    columns_duplication: str = str(info["columns"])
    columns_nulls: str = str(info["nullColumns"])
    actuality: str = str(info["actuality"])

    cron = scheduler_parser(time, interval, repeats)
    url_api = f'https://{SERVER_HOST}/api/2.1/jobs/create'
    body = {
        "name": checker_name,
        "tasks": [
            {
                "task_key": checker_name,
                "notebook_task": {
                    "notebook_path": NOTEBOOK_PATH,
                    "base_parameters": {
                        "db": db_name,
                        "table": table_name,
                        "checkers": checkers,
                        "filtration_condition": filtration_condition,
                        "columns_duplication": columns_duplication,
                        "columns_nulls": columns_nulls,
                        "actuality": actuality
                    },
                    "source": "WORKSPACE"
                },
                "existing_cluster_id": CLUSTER_ID
            }],
        "schedule": {
            "quartz_cron_expression": f"{cron}",
            "timezone_id": "Europe/London"
        },
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK",
    }

    response = await dbfs_rpc(url_api, body)

    return response
