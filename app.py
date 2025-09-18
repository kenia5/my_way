from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from helpers import get_db_connection, bug, delete_item
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Configurar la sesión para utilizar el sistema de archivos (en lugar de cookies firmadas)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# MANEJADOR DE ERRORES: Se ejecuta cada vez que se llame a abort
@app.errorhandler(400)
def handle_had_request(e):
    return render_template("bug.html", error_code=400, error_message=e.description), 400

@app.route("/register", methods = ["GET", "POST"])
def register():
    #Identificar al usuario
    if request.method == "GET":
        return render_template("register.html")
    
    # Insertar al usuario a la base de datos
    try:
        #Obtener una conexión a la base de datos
        db = get_db_connection()

        # Crear un cursor para ejecutar comandos SQL
        cursor= db.cursor()

        # Envio del nombre de usuario
        username = request.form.get("username")
        if not username or not username.strip():
            return bug("Incorrect username")

        # Envio de la contraseña
        password = request.form.get("password")
        if not password or not password.strip():
            return bug("Incorrect password")
        
        # Envio de la confirmacion de la contraseña
        confirmation = request.form.get("confirmation")
        if not confirmation or not confirmation.strip():
            return bug("Incorrect confirmation")
        
        # Contraseña y confirmación coincidan
        if password != confirmation:
            return bug("Passwords do not match")

        #Crear una contraseña única
        hash_password = generate_password_hash(password)

        cursor.execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (username, hash_password))
        
        # Guardar los cambios en la base de datos
        db.commit()

        # Obtener ID del nuevo registro
        user_id = cursor.lastrowid

        # Usario inicie sesión
        session["user_id"] = user_id

        # Página de inicio
        return redirect("/")
        
    except Exception as e:
        print(f"Error al insertar usuario: {e}")
        return bug("Username already exists")
        
    finally:
        db.close()

@app.route("/")
def index():
    # Verificar si el usuario está conectado
    if "user_id" not in session:
        return redirect("/login")
    
    db = None
    try: 
        db = get_db_connection()
        cursor = db.cursor()
        user_id = session["user_id"]

        # Obtener todas las metas del usuario actual
        goals = cursor.execute("SELECT * FROM goals WHERE user_id = ?", (user_id,)).fetchall()
        
        #Crear una nueva lista para almacenar todas las  metas con proyectos y tareas anidadas 
        goals_with_data = []

        #Iterar sobre cada meta
        for goal in goals:
            # Convertir la fila a un diccionario, para que sea mutable 
            goal_dict = dict(goal)

            # Obtener los proyectos para la meta actual
            projects = cursor.execute("SELECT * FROM projects WHERE goal_id = ?", (goal['id'],)).fetchall()

            #Crear una nueva lista para los proyectos con sus tareas
            projects_with_tasks=[]

            #Iterar sobre cada proyecto para obtener sus tareas
            for project in projects:
                project_dict=dict(project)

                tasks=cursor.execute("SELECT * FROM tasks WHERE project_id = ?", (project['id'],)).fetchall()

                #Anidar las tareas dentro del diccionario del proyecto
                project_dict['tasks'] = tasks

                #Agregar el proyecto con  sus tareas a la lista de proyectos
                projects_with_tasks.append(project_dict)
            
            # Agregar la lista de proyectos al diccionario
            goal_dict['projects'] = projects_with_tasks

            # Agregar el diccionario a la nueva lista
            goals_with_data.append(goal_dict)

        return render_template("index.html", goals=goals_with_data)
        
    except Exception as e:
        print(f"Error al cargar las metas: {e}")
        return bug("Could not load the targets")
    finally:
        if db:
            db.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "GET":
        return render_template("login.html")
    
    db = None
    try:
        # Abrir la base de datos
        db = get_db_connection()
        cursor = db.cursor()

        if not request.form.get("username"):
            return bug("Incorrect username")
            
        if not request.form.get("password"):
            return bug("Incorrect password")
            
        rows = cursor.execute("SELECT * FROM users WHERE username = ?", (request.form.get("username"),)).fetchall()

        if len(rows) != 1 or not check_password_hash(rows[0]["password_hash"], request.form.get("password")):
            return bug("Invalid username or password")
            
        # El usuario se ha conectado
        session["user_id"] = rows[0]["id"]

        return redirect("/")
        
    except Exception as e:
        print(f"Error al ingresar: {e}")
        return bug("Error logging in")
        
    finally:
        db.close()

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/add/goal", methods=["GET", "POST"])
def add_goal():
    if "user_id" not in session:
        return redirect("/login")

    if request.method=="GET":
        return render_template("add_goal.html")
    
    elif request.method == "POST":
        db = None
        try:
            db = get_db_connection()
            cursor = db.cursor()
            user_id = session["user_id"]
            title = request.form.get("title")
            if not title or not title.strip():
                return bug("No title. Add title")
            description = request.form.get("description")
            # CORREGIDO: Guarda None si el campo de fecha está vacío
            objective = request.form.get("objective") if request.form.get("objective") else None

            # Insertar la meta
            cursor.execute("INSERT INTO goals(user_id, title, description, objective) VALUES (?, ?, ?, ?)", (user_id, title, description, objective))
            db.commit()

            # Obtener el ID de la meta recien creada
            goal_id = cursor.lastrowid

            return redirect(f"/add/project/{goal_id}")
    
        except Exception as e:
            print(f"Error al agregar una meta: {e}")
            return bug("The target could not be added")

        finally:
            db.close()

@app.route("/add/project/<int:goal_id>", methods = ["GET", "POST"]) # La URL necesita el ID de la meta
def add_project(goal_id):
    if "user_id" not in session:
        return redirect("/")
    
    db = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        user_id = session["user_id"]

        # Verificar que el goal_id pertenece al usuario actual
        goal = cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id)).fetchone()
        if not goal:
            return bug("Goal not found")
        
        # Lógica para mostrar el formulario (GET)
        if request.method == "GET":
            return render_template("add_project.html", goal_id=goal['id'], goal_title=goal['title'])

        # Lógica para procesar el formulario (POST)
        elif request.method == "POST":
            title = request.form.get("title")
            if not title or not title.strip():
                return bug("No title. Add one")
            description = request.form.get("description")
            # CORREGIDO: Guarda None si el campo de fecha está vacío
            objective = request.form.get("objective") if request.form.get("objective") else None

            # Insertar el proyecto
            cursor.execute("INSERT INTO projects(goal_id, title, description, objective) VALUES(?, ?, ?, ?)", (goal['id'], title, description, objective))
            db.commit()

            project_id=cursor.lastrowid

            return redirect(f"/add/task/{project_id}")
    
    except Exception as e:
        print(f"Error al agregar proyecto: {e}")
        return bug("The project cannot be added. Please try again")
    
    finally:
        if db:
            db.close()

@app.route("/add/task/<int:project_id>", methods=["GET", "POST"])
def add_task(project_id):
    # Verificación de seguridad
    if "user_id" not in session:
        return redirect("/")

    db = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        user_id = session["user_id"]

        # Obetener el proyecto de la tabla 'projects'
        project = cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        # Si no lo encuentra, mostrar error
        if not project:
            return bug("Project not found")
        
        # Usar el goal_id del proyecto para verificar que la meta pertenece al usuario
        goal = cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (project['goal_id'], user_id)).fetchone()
        if not goal:
            return bug("Project not found or does not belong to the user")
        
        # Lógica para mostrar el formulario (GET)
        if request.method == "GET":
            return render_template("add_task.html", project_id=project['id'], project_title=project['title'])

        # Lógica para procesar el formulario (POST)
        elif request.method == "POST":
            title = request.form.get("title")
            if not title or not title.strip():
                return bug("No title. Add one")
            description = request.form.get("description")
            
            # CORREGIDO: Guarda None si el campo de fecha está vacío
            expiration_date = request.form.get("expiration_date") if request.form.get("expiration_date") else None
            # Ya lo tenías corregido, pero lo dejo para que veas que funciona
            priority = request.form.get("priority") if request.form.get("priority") else "No hay prioridad"

            # Insertar el proyecto
            cursor.execute("INSERT INTO tasks(project_id, title, description, expiration_date, priority) VALUES(?, ?, ?, ?, ?)", (project['id'], title, description, expiration_date, priority))
            db.commit()

            return redirect("/")
    
    except Exception as e:
        print(f"Error al agregar tarea: {e}")
        return bug("The project cannot be added. Please try again")
    
    finally:
        if db:
            db.close()
    
@app.route("/remove/goal/<int:goal_id>", methods=["POST"])
def remove_goal(goal_id):
    if "user_id" not in session:
        return redirect("/")
    
    delete_item("goal", goal_id)
    return redirect("/")

@app.route("/remove/project/<int:project_id>", methods=["POST"])
def remove_project(project_id):
    if "user_id" not in session:
        return redirect("/")
    
    #Llamada al helper
    delete_item("project", project_id)
    #redirigir
    return redirect("/")

@app.route("/remove/task/<int:task_id>",methods=["POST"])
def remove_task(task_id):
    if "user_id" not in session:
        return redirect("/")
    
    delete_item("task", task_id)
    return redirect("/")

@app.route("/complete/state/<item_type>/<int:item_id>", methods=["GET", "POST"])
def complete_item(item_type, item_id):
    if "user_id" not in session:
        return redirect("/")
    
    db=None
    try:
        db = get_db_connection()
        cursor=db.cursor()
        user_id=session["user_id"]

        #Actualizar el estado del elemento
        points_to_add=0
        if item_type == "goal":
            cursor.execute("UPDATE goals SET state = 'Complete' WHERE id = ?", (item_id,))
            points_to_add=100
        elif item_type == "project":
            cursor.execute("UPDATE projects SET state = 'Complete' WHERE id = ?", (item_id,))
            points_to_add=50
        elif item_type =="task":
            cursor.execute("UPDATE tasks SET state = 'Complete' WHERE id = ?", (item_id,))
            points_to_add=10
        else:
            db.commit()
            return redirect("/")
        #Sumar los puntos al usuario

        current_points_row=cursor.execute("SELECT total_points FROM users WHERE id=?",(user_id,)).fetchone()
        current_points=current_points_row['total_points']

        #Calcular el nuevo total de puntos
        new_total_points=current_points+points_to_add

        #Actualizar los puntos del usuario en la base de datos
        cursor.execute("UPDATE users SET total_points = ? WHERE id = ?",(new_total_points, user_id))

        db.commit()

        return redirect("/")
        
    except Exception as e:
        print(f"Error al completar el elemento: {e}")
        return bug("Could not be marked as complete. Please try again.")
    
    finally:
        if db:
            db.close()
    
@app.route("/points")
def points():
    if "user_id" not in session:
        return redirect("/")

    try:
        db = get_db_connection()
        cursor=db.cursor()
        user_id=session["user_id"]

        current=cursor.execute("SELECT total_points, current_level FROM users WHERE id = ?", (user_id,)).fetchone()
        points = current['total_points']
        level=current['current_level']

        # Subir de nivel
        while points >= (level* 100):
            #Sumar 1 al nivel
            level+=1
            #Restar la cantidad de puntos gastados para el nivel anterior
            points -= (level-1) * 100

        # Actualizar la base de datos
        cursor.execute("UPDATE users SET total_points=?, current_level=? WHERE id = ?", (points, level,user_id))
        db.commit()
        return  render_template("points.html", points=points, level=level)
    
    except Exception as e:
        print(f"No se puede cargar lospuntos y niveles: {e}")
        return bug("It is not possible to load points and levels.")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    app.run(debug=True)