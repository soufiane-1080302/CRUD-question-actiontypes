import hashlib
from collections import Counter
from datetime import datetime

from flask import render_template, request, redirect, url_for, session, jsonify
from flask_login import login_required, logout_user, login_user
from sqlalchemy import text

from statement_system import app, db
from statement_system.models import Students, Admin, Statements, StudentAnswers


@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Haal gegevens op uit het formulier
        username = request.form.get('name')
        password = request.form.get('password')
        repeat_password = request.form.get('repeat_password')

        # Valideer wachtwoorden
        if password != repeat_password:
            return render_template('signup.html', error="Passwords do not match")

        # Hash het wachtwoord voordat u het opslaat
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Maak een nieuw beheerdersrecord
        new_user = Admin(username=username, password=hashed_password, is_admin=False)
        db.session.add(new_user)
        db.session.commit()

        # Omleiding naar inloggen na succesvolle aanmelding
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Retrieve the form data
        username = request.form.get('username')
        password = request.form.get('password')

        # Zoek de gebruiker in de database
        user = Admin.query.filter_by(username=username).first()

        # Hash het wachtwoord ter vergelijking
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Zorg ervoor dat de gebruiker bestaat en dat de gehashte wachtwoorden overeenkomen
        if user and user.password == hashed_password:
            # Bewaar de gebruikersinformatie in de sessie
            session['user_id'] = user.admin_id
            session['username'] = user.username

            login_user(user)

            # Succesvol inloggen, doorverwijzen naar dashboard of startpagina
            return redirect(url_for('teacher_dashboard'))  # Wijzig 'dashboard' naar uw daadwerkelijke route
        else:
            # Failed login, return an error message
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')


@app.route('/teacher_dashboard', methods=['GET', 'POST'])
def teacher_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    total_students = Students.query.count()
    total_teachers = Admin.query.filter_by(is_admin=False).count()
    total_response = StudentAnswers.query.count()
    response_count = total_response / 20

    user_id = session.get('user_id')
    return render_template('index.html',
                           total_teachers=total_teachers,
                           total_students=total_students,
                           response_count=response_count)


@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        student_number = request.form.get('student_number')
        student = Students.query.filter_by(student_number=student_number).first()
        if student:
            session['student_number'] = student_number
            # Omleiding naar het eindpunt dat de HTML-pagina bedient, niet de JSON-gegevens
            return redirect(url_for('questions'))  # Update dit naar het juiste eindpunt
        else:
            return render_template('student.html', error="Student ID not found.")
    else:
        return render_template('student.html')


@app.route('/questions', methods=['GET'])
def questions():
    if 'student_number' not in session:
        return redirect(url_for('student'))

    student_number = session['student_number']
    current_user = Students.query.filter_by(student_number=student_number).first()
    total_statements = Statements.query.count()
    total_questions = total_statements // 2  # Omdat elke vraag een paar uitspraken is

    return render_template(
        'questions.html',
        student_number=student_number,
        current_user=current_user,
        total_questions=total_questions
    )


@app.route('/api/student/<int:student_number>/statement', methods=['GET'])
def get_statement(student_number):
    # Controleer of de leerling bestaat
    student = Students.query.filter_by(student_number=student_number).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    # Controleer of alle vragen zijn beantwoord
    total_statements = Statements.query.count()
    answered_statements = StudentAnswers.query.filter_by(student_number=student_number).count()
    if answered_statements >= total_statements:
        return jsonify({'error': 'All questions answered'}), 404

    # Bepaal de huidige verklaringsindex
    last_answer = StudentAnswers.query.filter_by(student_number=student_number).order_by(
        StudentAnswers.timestamp.desc()).first()

    if last_answer:
        if last_answer.statement_number % 2 == 0:
            current_statement_number = last_answer.statement_number + 1  # Ga naar de volgende verklaring
        else:
            current_statement_number = last_answer.statement_number + 2  # Ga naar het volgende paar
    else:
        current_statement_number = 1  # Begin met de eerste verklaring

    print(current_statement_number)

    # Haalt het stellingpaar op
    group_id = (current_statement_number + 1) // 2  # Berekent group_id
    first_statement = Statements.query.filter_by(group_id=group_id, statement_number=current_statement_number).first()
    second_statement = Statements.query.filter_by(group_id=group_id,
                                                  statement_number=current_statement_number + 1).first()

    return jsonify({
        "statement_number": current_statement_number,
        "total_statements": total_statements,  # Neem het totale aantal uitspraken op in het antwoord
        "statement_choices": [
            {
                "choice_number": first_statement.choice_number if first_statement else None,
                "choice_text": first_statement.choice_text if first_statement else None
            },
            {
                "choice_number": second_statement.choice_number if second_statement else None,
                "choice_text": second_statement.choice_text if second_statement else None
            }
        ]
    })


@app.route('/api/student/<int:student_number>/statement/<int:statement_number>/group/<int:group_id>', methods=['POST'])
def save_student_choice(student_number, statement_number, group_id):
    data = request.get_json()

    # Valideer het studentnummer en het rekeningafschriftnummer
    student = Students.query.filter_by(student_number=student_number).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    # Krijg de keuze van de verzoekinstantie
    statement_choice = data.get('statement_choice')
    if statement_choice is None:
        return jsonify({'error': 'Invalid request, statement_choice missing'}), 400

    if statement_choice == "2":
        statement_number += 1

    # Haal de afschriftdetails op uit de afschriftentabel
    statement = Statements.query.filter_by(group_id=group_id, statement_number=statement_number).first()
    if not statement:
        return jsonify({'error': 'Statement not found'}), 404

    # Bewaar de keuze van de student in StudentAnswers samen met choice_text en choice_result
    student_answer = StudentAnswers(
        student_number=student_number,
        statement_number=statement.statement_number,  # Haal het exacte statement_number op
        answer_group_id=group_id,
        answer_choice=statement_choice,
        answer_text=statement.choice_text,  # Keuze_tekst ophalen
        answer_result=statement.choice_result,  # Keuze_resultaat ophalen
        timestamp=datetime.utcnow()
    )

    db.session.add(student_answer)
    db.session.commit()

    return jsonify({"result": "ok"})


@app.route('/api/student/<int:student_number>/answers', methods=['GET'])
def get_student_answers(student_number):
    # Haal de antwoorden van studenten op uit de database op basis van studentnummer
    student_answers = StudentAnswers.query.filter_by(student_number=student_number).all()

    # Converteer antwoorden van studenten naar een lijst met woordenboeken
    answers = [{
        'question_number': answer.answer_group_id,
        'answer_result': answer.answer_result
    } for answer in student_answers]

    # Retourneer de antwoorden van de leerling als JSON-antwoord
    return jsonify({'answers': answers})



@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        # Haal de formuliergegevens op
        student_number = request.form.get('student_number')
        student_name = request.form.get('student_name')
        student_class = request.form.get('student_class')

        # Maak een nieuw studentenrecord aan in de database
        new_student = Students(student_number=student_number, student_name=student_name, student_class=student_class)
        db.session.add(new_student)
        db.session.commit()

        # Redirect of render een succespagina
        return redirect(url_for('add_student'))  # Verander indien nodig

    all_students = Students.query.all()

    # Haal de laatste tijdstempel voor elke student op uit StudentAnswers
    latest_timestamps = {}
    for student in all_students:
        latest_answer = StudentAnswers.query.filter_by(student_number=student.student_number).order_by(
            StudentAnswers.timestamp.desc()).first()
        latest_timestamps[student.student_number] = latest_answer.timestamp if latest_answer else None

    # Bereken de vraagstatus voor elke student
    for student in all_students:
        question_count = StudentAnswers.query.filter_by(student_number=student.student_number).count()
        student.question_count = question_count

        # Bepaal het actietype
        if question_count == 0:
            student.action_type = "None"
        else:
            query = text('''
                SELECT sa.student_number, st.choice_result AS answer_result
                FROM student_answers sa
                INNER JOIN statements st ON sa.statement_number = st.statement_number
            ''')
            student_answers = db.session.execute(query)

            all_student_answers = [
                {
                    'student_number': row[0],
                    'answer_result': row[1]
                }
                for row in student_answers
            ]

            print([student_answer['answer_result'] for student_answer in all_student_answers])

        # Bepaal de vraagstatus
        if question_count == 0:
            student.question_status = "Not Taken"
        elif question_count == 20:
            student.question_status = "Completed"
        else:
            student.question_status = "Partial"

    # Render een pagina met het studentenformulier voor GET-verzoeken
    return render_template('add_student.html', all_students=all_students, latest_timestamps=latest_timestamps)


@app.route('/edit_student/<int:student_number>', methods=['GET', 'POST'])
def edit_student(student_number):
    student = Students.query.filter_by(student_number=student_number).first()
    if request.method == 'POST':
        # Haal de formuliergegevens op
        student_class = request.form.get('student_class')
        team = request.form.get('team_name')

        # Controleer of de klas- of teamnaam van de leerling is opgegeven
        if student_class or team:
            # Update het studentenrecord in de database
            if student_class:
                student.student_class = student_class
            if team:
                student.team = team
            db.session.commit()
            # Retourneer een JSON-antwoord dat succes aangeeft
            return jsonify({'message': 'Student record updated successfully'})
        else:
            # Retourneer een JSON-antwoord dat aangeeft dat er geen velden zijn opgegeven voor update
            return jsonify({'error': 'No fields provided for update'})

    # Geef het bewerkingsformulier weer met de leerlinggegevens
    return render_template('edit_student.html', student=student)


@app.route('/update_action_types', methods=['POST'])
def update_action_types():
    # Haal alle studentnummers op
    student_numbers = db.session.query(StudentAnswers.student_number).distinct().all()
    print(student_numbers)

    for student_number_tuple in student_numbers:
        student_number = student_number_tuple[0]

        # Haal studentantwoorden op voor het huidige studentnummer
        student_answers = StudentAnswers.query.filter_by(student_number=student_number).all()

        # Controleer of de leerling precies 20 records heeft
        if len(student_answers) == 20:
            # Tel het voorkomen van choice_result-waarden
            choice_results = [answer.answer_result for answer in student_answers]
            print(choice_results)
            choice_counts = Counter(choice_results)

            # Bepaal keuze_resultaat met maximaal aantal
            max_choice_result = max(choice_counts, key=choice_counts.get)

            # Update het actietype van de leerling
            student = Students.query.filter_by(student_number=student_number).first()
            if student:
                student.action_type = max_choice_result
        else:
            # Als de leerling geen 20 records heeft, stelt u action_type in op 'Geen'
            student = Students.query.filter_by(student_number=student_number).first()
            if student:
                student.action_type = 'None'

    # Wijzigingen in de database doorvoeren
    db.session.commit()

    # Retourneer een JSON-antwoord dat succes aangeeft
    return jsonify({'message': 'Action types updated successfully'})


@app.route('/student_answers', methods=['GET'])
def student_answers():
    # Haal de antwoorden van studenten op samen met relevante informatie uit de tabellen Studenten en Verklaringen
    query = text('''
        SELECT sa.student_number, s.student_name, sa.answer_text, st.choice_text AS answer_text, st.choice_result AS answer_result, sa.timestamp AS date_filled
        FROM student_answers sa
        INNER JOIN students s ON sa.student_number = s.student_number
        INNER JOIN statements st ON sa.statement_number = st.statement_number
    ''')
    student_answers = db.session.execute(query)

    # Converteer het zoekresultaat naar een lijst met woordenboeken voor gemakkelijke toegang in de sjabloon
    all_student_answers = [
        {
            'student_number': row[0],
            'student_name': row[1],
            'answer_text': row[3],
            'answer_result': row[4],
            'date_filled': row[5]
        }
        for row in student_answers
    ]

    return render_template('student_answers.html', all_student_answers=all_student_answers)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))  # Redirect naar login toe



@app.route("/manage_teacher", methods=['GET', 'POST'])
def manage_teacher():

    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        is_admin = True if request.form.get("is_admin") else False

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        new_admin = Admin(username=username, password=hashed_password, is_admin=is_admin)
        db.session.add(new_admin)
        db.session.commit()

        return redirect(url_for("manage_teacher"))

    teachers = Admin.query.all()

    return render_template("manage_teacher.html"
                           , all_teachers=teachers)


@app.route("/delete_teacher/<teacher_id>")
def delete_teacher(teacher_id):
    teacher = Admin.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    return redirect(url_for("manage_teacher"))