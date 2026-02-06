"""
Cloud SQL Connection Helper using Google Cloud SQL Python Connector
This is the recommended way to connect to Cloud SQL from Cloud Run
"""
import os
import sqlalchemy
from google.cloud.sql.connector import Connector

def get_cloud_sql_engine():
    """Create SQLAlchemy engine using Cloud SQL Connector"""
    
    # Cloud SQL connection details
    instance_connection_name = "quantsight-prod:us-central1:quantsight-db"
    db_user = "quantsight"
    db_pass = "QSInvest2026"
    db_name = "nba_data"
    
    # Initialize Cloud SQL Python Connector
    connector = Connector()
    
    def getconn():
        conn = connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
        )
        return conn
    
    # Create SQLAlchemy engine
    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    
    return engine
