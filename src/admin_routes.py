from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
import pyodbc
from src.database import Database

# Create a Blueprint for admin routes
admin_blueprint = Blueprint('admin', __name__)

# Database connection
connection_string = 'DRIVER={ODBC Driver 11 for SQL Server};SERVER=DESKTOP-UTI2QK7\\SQLEXPRESS;DATABASE=Platform;Trusted_Connection=yes;'
db = Database(connection_string)

# show Student and Teacher tables
@admin_blueprint.route('/admin_db/<table>', methods=['GET'])
def show_tables(table):
    allowed_tables = ['Student', 'Teacher']
    if table not in allowed_tables:
        return jsonify({'message': 'Admin Route: Invalid table route.'}), 400
    query = f"SELECT * FROM {table}"
    cursor = db.execute_query(query)
    object_list = db.extract_data(cursor)
    return render_template(str(table) + '.html', objects=object_list)

@admin_blueprint.route('/get_columns', methods=['GET'])
def get_columns():
    table = request.args.get('table')
    query = f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}'"
    cursor = db.execute_query(query)
    columns = [row[0] for row in cursor.fetchall()][1:] # skip first column = ID
    return jsonify(columns)

# Admin erase data route
@admin_blueprint.route('/admin_erase_data', methods=['POST'])
def admin_erase_data():
    table = request.form['table']

    # delete student => delete from Student, StudentCoursesList
    if table == 'Student':
        record_id = request.form['StudentID']
        name = request.form['Name']
        surname = request.form['Surname']
        params = (record_id, name, surname)
        print(params)
        # delete from StudentCoursesList
        query = f"DELETE FROM StudentCoursesList WHERE StudentID = ?"
        db.execute_query(query, (record_id,), commit=True)
        # delete from Student
        query = "DELETE FROM Student WHERE StudentID = ? and Name = ? and Surname = ?"
        db.execute_query(query, params=params, commit=True)

    # delete teacher => delete from Teacher, Course
    elif table == 'Teacher':
        record_id = request.form['StudentID'] # same function as Student
        name = request.form.get('Name', None)
        surname = request.form.get('Surname', None)
        # delete from Course
        query = "DELETE FROM Course WHERE TeacherID = ?"
        db.execute_query(query, (record_id,), commit=True)
        # delete from Teacher
        query = "DELETE FROM Teacher WHERE TeacherID = ?"
        db.execute_query(query, (record_id,), commit=True)

    # delete course => delete from Course, StudentCoursesList, Exam, Category--, Student--, Teacher--
    elif table == 'Course':
        record_id = request.form['CourseID']
        # delete from StudentCoursesList, Exam
        query = f"DELETE FROM StudentCoursesList WHERE CourseID = ?"
        db.execute_query(query, (record_id,), commit=True)
        query = f"DELETE FROM Exam WHERE CourseID = ?"
        db.execute_query(query, (record_id,), commit=True)
        # delete from Course
        query = "DELETE FROM Course WHERE CourseID = ?"
        db.execute_query(query, (record_id,), commit=True)

        cursor_show_table = db.execute_query(
            """
            SELECT 
                c.Title AS CourseTitle,
                c.Category,
                c.Description,
                c.CourseCapacity,
                t.Name + ' ' + t.Surname AS TeacherName,
                t.Username AS TeacherUsername
            FROM Course c
            JOIN Teacher t ON c.TeacherID = t.TeacherID
            ORDER BY c.Title ASC, t.Name ASC;
            """)
        object_list = db.extract_data(cursor_show_table)
        return render_template('Course.html', courses=object_list)

    else:
        # default delete
        record_id = request.form['record_id']
        query = f"DELETE FROM {table} WHERE " + str(table) + "ID = ?"
        db.execute_query(query, (record_id,), commit=True)

    cursor_show_table = db.execute_query(f"SELECT * FROM {table}")
    object_list = db.extract_data(cursor_show_table)

    return render_template(str(table) + '.html', objects=object_list)

# Admin modify data route
@admin_blueprint.route('/admin_modify_data', methods=['POST'])
def admin_modify_data():
    # implement the modify data route
    table = request.form['table']
    column = request.form['column']

    print(column)

    # Ids cannot be modified
    table_name = table.capitalize()
    if column == table_name + 'ID':
        return jsonify({'message': 'Admin Route: Ids cannot be modified'}), 400

# FIX: afiseaza 2 text box-uri pentru ID din cauza var 'RecordID' modificat dinamic in functie de '{tabel}.html'

    # Modify Student
    if table == 'Student':
        record_id = request.form['StudentID'] # required
        name = request.form.get('Name', None) # not required
        surname = request.form.get('Surname', None) # not required
        query = f"UPDATE Student SET {column} = ? WHERE StudentID = ?"
        new_value = request.form['new_value']
        print(new_value, record_id)
        db.execute_query(query, (new_value, record_id), commit=True)

    # Modify Teacher
    elif table == 'Teacher':
        record_id = request.form['TeacherID']
        name = request.form.get('Name', None)
        surname = request.form.get('Surname', None)
        query = f"UPDATE Teacher SET {column} = ? WHERE TeacherID = ?"
        new_value = request.form['new_value']
        print(new_value, record_id)
        db.execute_query(query, (new_value, record_id), commit=True)
    
    # Modify Category => modify Course, AdmissionExam
    elif table == 'Category':
        record_id = request.form['CategoryID']
        title = request.form.get('Title', None) 
        
        # modify Course
        if column == 'Title':

            new_value = request.form['new_value']
            # modify Course
            query = f"UPDATE Course SET Category = ? WHERE Category = ?"
            db.execute_query(query, (new_value, record_id), commit=True)
            # modify AdmissionExam
            query = f"UPDATE AdmissionExam SET Category = ? WHERE Category = ?"
            db.execute_query(query, (new_value, record_id), commit=True)

        query = f"UPDATE Category SET {column} = ? WHERE CategoryID = ?"
        new_value = request.form['new_value']
        print(new_value, record_id)
        db.execute_query(query, (new_value, record_id), commit=True)
        # Fix: cere new_value de 2 ori

    # Modify Course
    elif table == 'Course':
        record_id = request.form['CourseID']
        title = request.form.get['Title', None]
        query = f"UPDATE Course SET {column} = ? WHERE CourseID = ?"
        new_value = request.form['new_value']
        print(new_value, record_id)
        db.execute_query(query, (new_value, record_id), commit=True)

        cursor_show_table = db.execute_query(f"SELECT * FROM {table}")
        object_list = db.extract_data(cursor_show_table)
        return render_template('Course.html', courses=object_list)
    
    # Default: modify other tables
    else:
        record_id = request.form['record_id']
        query = f"UPDATE {table} SET {column} = ? WHERE " + str(table) + "ID = ?"
    
    cursor_show_table = db.execute_query(f"SELECT * FROM {table}")
    object_list = db.extract_data(cursor_show_table)

    return render_template(str(table) + '.html', objects=object_list)