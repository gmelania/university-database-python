from flask import jsonify
import pyodbc

class Database:
    def __init__(self, connection_string):
        self.conn = pyodbc.connect(connection_string)
        self.conn.autocommit = True

    def execute_query(self, sql, params=None, commit=False):
        cursor = self.conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        if commit:
            self.conn.commit()
        return cursor
    
    def extract_data(self, cursor, objects=None):
        objects = cursor.fetchall()
        if not objects:
            return []
        
        object_list = []
        for obj in objects:
            obj_dict = {}
            for column in cursor.description:
                column_name = column[0]
                attr_value = cursor.description.index(column)
                obj_dict[column_name] = obj[attr_value]
            object_list.append(obj_dict)
        return object_list