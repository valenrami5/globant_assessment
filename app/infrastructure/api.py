from fastapi import FastAPI, UploadFile, File, HTTPException, status, Request, HTTPException
from typing import List, Dict
import pandas as pd
from app.domain.models.jobs import Jobs
from app.domain.models.departments import Departments
from app.infrastructure import azure_db_connector
import csv
from typing import Callable, List, Type
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import JSONResponse
from app.domain.models.hired_employees import HiredEmployees
from app.infrastructure.db_reader import EtlPivotedTable
from app.infrastructure.db_reader import MeanEmployeesHired
from fastapi.responses import HTMLResponse

app = FastAPI()
try:
    sql_manager = azure_db_connector.SqlManager()
except Exception as e:
    sql_manager = None
    print(f"Database connection failed: {e}")

def batch_insert_handler(model: Type[BaseModel], insert_method: Callable[[List[BaseModel]], None]):
    """
    Decorator for handling batch insertion of data into the AzureSQL dabase called (HR) Managment.

    Parameters:
        model (Type[BaseModel]): The type of the data model to be inserted.
        insert_method (Callable[[List[BaseModel]], None]): The method responsible for batch insertion.

    Returns:
        Callable: A decorated function that handles batch insertion of data.

    Raises:
        HTTPException: If there is an error processing the file or if the batch size is invalid.
    """
    def decorator(func: Callable):
        async def wrapper(file: UploadFile = File(...)):
            try:
                content = await file.read()
                content_str = content.decode('utf-8').splitlines()
                csv_reader = csv.reader(content_str)
                raw_data = [row for row in csv_reader]
                try:
                    objects = []
                    for item in raw_data:
                        
                        if model is Jobs:
                            obj = model(id=int(item[0]), job=item[1])
                        elif model is Departments:
                            obj = model(id=int(item[0]), department=item[1])
                        elif model is HiredEmployees:
                            obj = model(
                                    id=int(item[0]),
                                    name=item[1] if item[1] else None,
                                    datetime=datetime.strptime(item[2], "%Y-%m-%dT%H:%M:%SZ") if item[2] else None,
                                    department_id=int(item[3]) if item[3] else None,
                                    job_id=int(item[4]) if item[4] else None
                                )
                        else:
                            raise HTTPException(status_code=400, detail="Unsupported model type")
                        objects.append(obj)
                except Exception as e:
                    raise HTTPException(status_code=400, detail="Data types do not match")
                if sql_manager:
                    insert_method(objects)
                    return {"message": "Batch data uploaded successfully"}
                else:
                    raise HTTPException(status_code=500, detail="Database connection failed")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error processing file: {e}")
        return wrapper
    return decorator

@app.get("/assessment_1", response_class=HTMLResponse)
async def get_dataframe():
    df = EtlPivotedTable().transform_hired_employees()
    html = df.to_html()
    return HTMLResponse(content=html)

@app.get("/assessment_2", response_class=HTMLResponse)
async def get_dataframe():
    df = MeanEmployeesHired().transform_mean_employees()
    html = df.to_html()
    return HTMLResponse(content=html)

@app.get("/")
async def root():
    return {"message": "Welcome to HR Management API :)"}

@app.post("/upload-jobs/", status_code=status.HTTP_201_CREATED)
@batch_insert_handler(Jobs, sql_manager._insert_jobs_batch)
async def upload_jobs(file: UploadFile = File(...)):
    """
    Endpoint to upload job-related data in bulk.

    Parameters:
        file (UploadFile): A CSV file containing job data to be uploaded.

    Returns:
        dict: A dictionary containing a success message upon successful upload.

    Raises:
        HTTPException: If there is an error processing the file or if the batch size is invalid.

    """
    pass  

@app.post("/upload-departments/", status_code=status.HTTP_201_CREATED)
@batch_insert_handler(Departments, sql_manager._insert_departments_batch)
async def upload_departments(file: UploadFile = File(...)):
    """
    Endpoint to upload department-related data in bulk.

    Parameters:
        file (UploadFile): A CSV file containing department data to be uploaded.

    Returns:
        dict: A dictionary containing a success message upon successful upload.

    Raises:
        HTTPException: If there is an error processing the file or if the batch size is invalid.
    """
    pass  

@app.post("/upload-hired-employees/", status_code=status.HTTP_201_CREATED)
@batch_insert_handler(HiredEmployees, sql_manager._insert_hired_employees_batch)
async def upload_departments(file: UploadFile = File(...)):
    """
    Endpoint to upload hired employees-related data in bulk.

    Parameters:
        file (UploadFile): A CSV file containing hired employees data to be uploaded.

    Returns:
        dict: A dictionary containing a success message upon successful upload.

    Raises:
        HTTPException: If there is an error processing the file or if the batch size is invalid.
    """
    pass  

async def db_connection_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException) and exc.status_code == 500 and 'Database connection failed' in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": "Temporary server issue. Please try again later."},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected error occurred."},
    )
