import sys
import os

# parent dir added to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, redirect, render_template, request, url_for, jsonify, session
from admin_routes import admin_blueprint
from database import Database

app = Flask(__name__)
app.secret_key = 'adminpassword'
app.register_blueprint(admin_blueprint)

# Initialize database connection
connection_string = (
    'DRIVER={ODBC Driver 11 for SQL Server};'
    'SERVER=DESKTOP-UTI2QK7\\SQLEXPRESS;'
    'DATABASE=Platform;'
    'Trusted_Connection=yes;'
)
db = Database(connection_string)

@app.route('/signup', methods=['GET'])
def show_signup_form():
    return render_template('signup.html')

# post student account in StudentDB: entered student data + password
@app.route('/signup', methods=['POST'])
def signup_student():
    data = request.form

    # students must have stud.platform.ro and teachers must have teach.platform.ro
    if not data['Username'].endswith('@stud.platform.ro') and not data['Username'].endswith('@teach.platform.ro'):
        error = 'Invalid email address. Student accounts must contain \'@stud.platform.ro\' and teacher accounts must contain \'@teach.platform.ro\'.'
        return render_template('signup.html', error=error)
    
    table = 'Student' if data['Username'].endswith('@stud.platform.ro') else 'Teacher'

    # Find the last ID and increment it for the new user
    cursor = db.execute_query(f"SELECT MAX({table}ID) FROM {table}")
    result = cursor.fetchone()
    id = (result[0] + 1) if result else 1

    if table == 'Student':
        # Students have a CoursesNumber field
        query = "INSERT INTO Student (StudentID, Username, Password, CoursesNumber, Name, Surname) VALUES (?, ?, ?, 0, ?, ?)"
        params = (
            id,
            data['Username'],
            data['Password'],
            data['Name'],
            data['Surname'],
        )
        url = url_for('studashboard', student_id=id)
    else:
        query = "INSERT INTO Teacher (TeacherID, Username, Password, Name, Surname) VALUES (?, ?, ?, ?, ?)"
        params = (
            id,
            data['Username'],
            data['Password'],
            data['Name'],
            data['Surname'],
        )
        url = url_for('prodashboard', teacher_id=id)
    db.execute_query(query, params, commit=True)
    return redirect(url)
    # return jsonify({'message': 'Student signed up successfully!'})

@app.route('/db/<table>', methods=['GET'])
def get_table(table):
    blocked_tables = ['Student', 'Teacher']
    student_allowed_tables = ['Course', 'Exam', 'StudentCoursesList']

    if table not in blocked_tables + student_allowed_tables:
        return jsonify({'message': 'Invalid table route.'}), 400

    # Check if the table is blocked = requires admin credentials
    if table in blocked_tables:
        username = request.args.get('username')
        password = request.args.get('password')
        if username != 'admin' or password != 'adminpassword':
            return jsonify({'message': 'Admin credentials are required to access this table.'}), 401
        
    # Courses
    if table == 'Course':
        #5 Join: Toate cursurile disponibile (table: Course joined with Teacher) 
        cursor = db.execute_query(""" 
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
        object_list = db.extract_data(cursor)
        return render_template('Course.html', courses=object_list)

    try:
        cursor = db.execute_query(f"SELECT * FROM {table}")
        object_list = db.extract_data(cursor)
    except Exception as e:
        return jsonify({'message': 'Error executing query', 'error': str(e)}), 500

    if not object_list:
        return jsonify({'message': 'No data found'}), 404

    return render_template(f"{table}.html", objects=object_list)

@app.route('/reset_passwords_form', methods=['GET'])
def reset_passwords_form():
    return render_template('reset_passwords.html')

@app.route('/reset_passwords', methods=['POST'])
def reset_passwords():
    data = request.form
    query = "UPDATE Student SET Password = ? WHERE StudentID = ?"
    params = (data['Password'], data['StudentID'])
    db.execute_query(query, params, commit=True)
    return jsonify({'message': 'Password reset successfully!'})

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        password = request.form['password']

        if role == 'student':
            query = "SELECT * FROM Student WHERE Username = ? AND Password = ?"
            cursor = db.execute_query(query, (username, password))
            student = cursor.fetchone()
            if student:
                return redirect(url_for('studashboard', student_id=student.StudentID))
            else:
                error = "Student account not found."
                return render_template('login.html', error=error, show_register=True)
        elif role == 'professor':
            query = "SELECT * FROM Teacher WHERE Username = ? AND Password = ?"
            cursor = db.execute_query(query, (username, password))
            teacher = cursor.fetchone()
            if teacher:
                return redirect(url_for('prodashboard', teacher_id=teacher.TeacherID))
            else:
                error = "Professor account not found."
                return render_template('login.html', error=error, show_register=True)
        elif role == 'admin':
            if username == 'admin' and password == 'adminpassword':
                return render_template('admin_dashboard.html')
            else:
                error = "Invalid admin credentials."
                return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/dashboard/student/<int:student_id>')
def studashboard(student_id):
    query_student = "SELECT * FROM Student WHERE StudentID = ?"

    student_cursor = db.execute_query(query_student, (student_id,))
    student = student_cursor.fetchone()

    #1 JOIN: Interogare pentru toate cursurile studentului
    cursor_courses = db.execute_query("""
        SELECT 
            c.Title, c.Category, SL.Grade, c.Description, 
            t.Name + ' ' + t.Surname AS TeacherName
        FROM StudentCoursesList SL
        JOIN Student s ON s.StudentID = SL.StudentID
        JOIN Course c ON c.CourseID = SL.CourseID
        JOIN Teacher t ON c.TeacherID = t.TeacherID
        WHERE s.StudentID = ?
    """, (student_id,))

    courses = db.extract_data(cursor_courses)

    #3 JOIN: Interogare pentru toate examenele studentului
    exams_cursor = db.execute_query("""
        SELECT 
            c.Title, 
            e.Date, e.Time, e.Required, 
            SL.Grade
        FROM Exam e
        JOIN Course c ON c.CourseID = e.CourseID
        JOIN StudentCoursesList SL ON SL.CourseID = c.CourseID
        WHERE SL.StudentID = ?
    """, (student_id,))

    exams = db.extract_data(exams_cursor)

    exams_sorted = {'scheduled': [], 'passed': [], 'failed': []}
    for exam in exams:
        if exam['Grade'] is None:
            exams_sorted['scheduled'].append(exam)
        elif exam['Grade'] >= 50:
            exams_sorted['passed'].append(exam)
        else:
            exams_sorted['failed'].append(exam)
    # join cu nota studentului, Course si StudentCoursesList
    cursor_student_courses = db.execute_query("""
        SELECT 
            s.Name + ' ' + s.Surname AS StudentName, 
            c.Title AS CourseTitle, 
            c.Category, 
            SL.Grade
        FROM StudentCoursesList SL
        JOIN Student s ON s.StudentID = SL.StudentID
        JOIN Course c ON c.CourseID = SL.CourseID
        WHERE s.StudentID = ?
    """, (student_id,))

    student_courses_list = db.extract_data(cursor_student_courses)

    # Join cu teacher si course -> media cursului, nota studentului, cursul si numele profesorului
    cursor_course_avg = db.execute_query("""
        SELECT 
            c.Title AS CourseTitle, 
            t.Name + ' ' + t.Surname AS TeacherName, 
            AVG(SL.Grade) AS CourseAverageGrade, 
            SL.Grade AS StudentGrade
        FROM StudentCoursesList SL
        JOIN Course c ON c.CourseID = SL.CourseID
        JOIN Teacher t ON t.TeacherID = c.TeacherID
        WHERE SL.StudentID = ?
        GROUP BY c.Title, t.Name, t.Surname, SL.Grade
    """, (student_id,))

    course_avg_list = db.extract_data(cursor_course_avg)

    # Join cu Student si StudentCoursesList si Course -> media notelor studentului
    cursor_student_course_avg = db.execute_query("""
        SELECT 
            s.Name + ' ' + s.Surname AS StudentName, 
            c.Title AS CourseTitle, 
            AVG(SL.Grade) AS AverageGrade
        FROM StudentCoursesList SL
        JOIN Student s ON s.StudentID = SL.StudentID
        JOIN Course c ON c.CourseID = SL.CourseID
        WHERE s.StudentID = ?
        GROUP BY s.Name, s.Surname, c.Title
    """, (student_id,))

    student_course_avg_list = db.extract_data(cursor_student_course_avg)

    # Calculul notei medii
    #1 Subcerere:  Afișează media notelor pentru studentul s.Name (table: StudentCoursesList) 
    cursor_avg = db.execute_query(""" 
        SELECT  
            s.StudentID, 
            s.Name + ' ' + s.Surname AS StudentName, 
            ( 
                SELECT AVG(SL.Grade)
                FROM StudentCoursesList SL 
                WHERE SL.StudentID = s.StudentID 
            ) AS AverageGrade 
        FROM  
            Student s 
        WHERE  
            s.StudentID = ?; 
        """, (student_id,))
    avg_grade = db.extract_data(cursor_avg)[0]['AverageGrade']

    if student:
        return render_template('studashboard.html', 
                               student=student,  
                                courses=courses,
                                exams=exams_sorted,
                                average_grade=avg_grade,
                                student_courses_list=student_courses_list,
                                course_avg_list=course_avg_list,
                                student_course_avg_list=student_course_avg_list)
    else:
        return "Student not found", 404

@app.route('/dashboard/teacher/<int:teacher_id>')
def prodashboard(teacher_id):
    query_teacher = "SELECT * FROM Teacher WHERE TeacherID = ?"
    teacher_cursor = db.execute_query(query_teacher, (teacher_id,))
    teacher = teacher_cursor.fetchone()

    query_courses = "SELECT * FROM Course WHERE TeacherID = ?"
    courses_cursor = db.execute_query(query_courses, (teacher_id,))
    courses = db.extract_data(courses_cursor)

    #2 JOIN: Toate cursurile profesorului
    query_students = """
        SELECT c.Title as Course, s.Name + ' ' + s.Surname as Student, SL.Grade, s.Username
        FROM StudentCoursesList SL
        JOIN Student s ON s.StudentID = SL.StudentID
        JOIN Course c ON c.CourseID = SL.CourseID
        WHERE c.TeacherID = ?
        ORDER BY c.Title ASC, s.Name ASC
    """
    students_cursor = db.execute_query(query_students, (teacher_id,))
    students = db.extract_data(students_cursor)

    #2 Subcerere: Stud inscrisi la cursurile profesorului c.Teacher, passed stud + course pass rate
    query_exams = """
        SELECT e.ExamID, c.Title as Course, e.Date, e.Time, e.Required,
               (SELECT COUNT(*) FROM StudentCoursesList SL WHERE SL.CourseID = c.CourseID) as TotalStudents,
               (SELECT COUNT(*) FROM StudentCoursesList SL WHERE SL.CourseID = c.CourseID AND SL.Grade >= 50) as PassedStudents,
               (SELECT (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM StudentCoursesList SL WHERE SL.CourseID = c.CourseID)) FROM StudentCoursesList SL WHERE SL.CourseID = c.CourseID AND SL.Grade >= 50) as PassRate
        FROM Exam e
        JOIN Course c ON c.CourseID = e.CourseID
        WHERE c.TeacherID = ?
    """
    exams_cursor = db.execute_query(query_exams, (teacher_id,))
    exams = db.extract_data(exams_cursor)

    #3 Subcerere cu select count pentru a calcula cati profesori si cati studenti sunt in baza de date si cate cursuri sunt
    cursor_count = db.execute_query("""
        SELECT
            (SELECT COUNT(*) FROM Teacher) AS TeachersCount,
            (SELECT COUNT(*) FROM Student) AS StudentsCount,
            (SELECT COUNT(*) FROM Course) AS CoursesCount
    """)
    count = db.extract_data(cursor_count)

    #4 Subcerere: Afișează media notelor pe toate cursurile sale, pentru profesorul t.Name (table: Course)
    cursor_avg = db.execute_query(""" 
        SELECT  
            t.Name + ' ' + t.Surname AS TeacherName, 
            ( 
                SELECT AVG(SL.Grade)
                FROM StudentCoursesList SL 
                JOIN Course c ON c.CourseID = SL.CourseID 
                WHERE c.TeacherID = t.TeacherID 
            ) AS AverageGrade 
        FROM  
            Teacher t 
        WHERE  
            t.TeacherID = ?; 
        """, (teacher_id,))

    
    avg_grade = db.extract_data(cursor_avg)
    

    if teacher:
        return render_template('prodashboard.html', teacher=teacher, courses=courses, students=students, exams=exams, count=count, avg_grade=avg_grade)
    else:
        return "Teacher not found", 404
    
# calendar route for exams per day
@app.route('/calendar', methods=['GET', 'POST'])
def get_calendar_data():
    error = None
    exams = []
    selected_date = None
    if request.method == 'POST':
        selected_date = request.form['selected_date']
        print(selected_date)

        #6 Join: Interogare pentru examenele programate pentru data selectata
        cursor = db.execute_query(""" 
                        SELECT  
                            c.Title AS CourseTitle, 
                            e.Date AS Date, 
                            e.Time AS Time, 
                            e.Required 
                        FROM Course c 
                        JOIN Exam e ON c.CourseID = e.CourseID 
                        WHERE e.Date = ?; 
                    """, (selected_date,))

        exams = db.extract_data(cursor)
        print(exams)
        if exams == []:
            error = "No exams scheduled for the selected date."

    return render_template('calendar.html', error=error, data=exams, selected_date=selected_date)

if __name__ == '__main__':
    app.run(debug=True)
