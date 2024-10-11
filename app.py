import os
from flask import Flask, render_template, redirect, request, flash
from flask import Response, session, url_for, jsonify
from flask_mysqldb import MySQL
import bcrypt #para el hashing del password
import hashlib

app = Flask(__name__)

MONEDA = 'S/. '
KEY_TOKEN = 'APR.wqc-354*'
app.secret_key = 'user54321'
app.config['MYSQL_HOST'] = "localhost"
app.config['MYSQL_USER'] = "root"
app.config['MYSQL_PASSWORD'] = ""
app.config['MYSQL_DB'] = "alpamayo"

mysql = MySQL(app)

def generate_token(id):
    token = f"{id}{KEY_TOKEN}"
    return hashlib.sha1(token.encode()).hexdigest()

def verify_token(id, token):
    return generate_token(id) == token

@app.route('/')
def index():
    return render_template ('index.html')

@app.route('/catalogo')
def catalogo():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, precio FROM productos WHERE activo = 1")
    resultados = cur.fetchall()
    MONEDA = 'S/.'
    productos = []

    for row in resultados:
        id = row[0]
        nombre = row[1]
        precio = row[2]

        # Verificar si la imagen existe
        imagen = f"img/productos/{id}/item.png"
        imagen_path = os.path.join('static', imagen)
        if not os.path.exists(imagen_path):
            imagen = "img/no-imagen.jpg"

        token = generate_token(id)
        productos.append({'id': id, 'nombre': nombre, 'precio': precio,'imagen': imagen, 'token': token })
    cur.close()

    return render_template('catalogo.html', productos = productos, MONEDA = MONEDA)

@app.route('/producto/<int:id>/<token>')
def detalles_producto(id, token):
    # Validar el token
    if not verify_token(id, token):
        flash("Error al procesar la petición", "danger")
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    # Consultar si el producto existe
    cur.execute("SELECT COUNT(id) FROM productos WHERE id = %s AND activo = 1", (id,))
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT id, nombre, descripcion, precio, descuento FROM productos WHERE id = %s AND activo = 1 LIMIT 1", (id,))
        row = cur.fetchone()
        
        if row:
            nombre = row[1]
            descripcion = row[2]
            precio = row[3]
            descuento = row[4]
            precio_desc = precio - ((precio * descuento) / 100)
            # Verificar si la imagen existe
            imagen = f"img/productos/{id}/item.png"
            imagen_path = os.path.join('static', imagen)
            if not os.path.exists(imagen_path):
                imagen = "img/no-imagen.jpg"
        else:
            flash("Producto no encontrado", "warning")
            return redirect(url_for('catalogo'))  # Redirigir si no se encuentra el producto
    else:
        flash("Producto no encontrado", "warning")
        return redirect(url_for('catalogo'))  # Redirigir si no se encuentra el producto

    cur.close()
    
    return render_template('detalles_producto.html', MONEDA=MONEDA, nombre=nombre, precio=precio, descuento=descuento, descripcion=descripcion, precio_desc=precio_desc, imagen=imagen, id=id)

@app.route('/login', methods=['GET', 'POST']) #GET y POST para el FORM
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        cur = mysql.connection.cursor()
        
        #Verificamos si el usuario y la contraseña ingresada son validas 
        cur.execute ("SELECT id, usuario, password, id_rol FROM clientes WHERE usuario = %s ", (usuario,))
        cuenta = cur.fetchone()
        if cuenta:
            hashed_password = cuenta[2]
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                session['logueado'] = True
                session['id_cliente'] = cuenta[0]
                session['id_rol'] = cuenta[3]

                if session['id_rol'] == 1:  #admin
                    return render_template('admin.html')
                
                elif session['id_rol'] == 2: #usuario
                    flash("Ingreso exitoso.", "success")
                    # Almacenar el nombre completo en la sesión
                    session['nombre_completo'] = f"{cuenta[1]} {cuenta[2]}"  # Nombres y apellidos

                    # Cargar los datos del carrito almacenado del cliente
                    cur.execute("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s", (cuenta[0],))
                    carrito = cur.fetchall()

                    # Guardar el carrito en la sesión
                    session['carrito'] = [{'producto_id': item[0], 'cantidad': item[1]} for item in carrito]
            else:
                flash("Usuario o contraseña incorrectos.", "danger")
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
        cur.close()
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST']) #GET y POST para el FORM
def registro():

    if request.method == 'POST':
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        email = request.form['email']
        telefono = request.form['telefono']
        dni = request.form['dni']
        usuario = request.form['usuario']
        password = request.form['password']
        repassword = request.form['repassword']

        cur = mysql.connection.cursor()

        try: 
            #Verificar si el usuario ya existe
            cur.execute ("SELECT * FROM clientes WHERE usuario = %s", [usuario])
            user_exists = cur.fetchone()
            if user_exists:
                flash("El nombre de usuario ya esta en uso.", "danger")
                return render_template('registro.html')
            #Verificar si el email ya esta en uso
            cur.execute ("SELECT * FROM clientes WHERE email = %s", [email])
            email_exists = cur.fetchone()
            if email_exists:
                flash("El email ya esta en uso.", "danger")
                return render_template('registro.html')
            
            if password != repassword:
                flash("Las contraseñas no coinciden.", "danger")
                return render_template ('registro.html')
        
            new_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
            cur.execute ("INSERT INTO clientes (nombres, apellidos, email, telefono, dni, estatus, fecha_atta, usuario, password) VALUES (%s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP, %s, %s)", (nombres, apellidos, email, telefono, dni, usuario, new_password))

            mysql.connection.commit()

            flash("Registro exitoso. Puedes iniciar sesión ahora.", "success")
        except Exception as e:
            flash(f"Error durante el registro: {str(e)}", "error")
            return render_template('registro.html')
        finally:
            cur.close()
    
    return render_template ('registro.html')

@app.route('/logout')
def logout():
    # Limpiar la sesión
    session.clear()
    flash("Has cerrado sesión exitosamente.", "success")
    return redirect(url_for('index'))  # Redirigir a la página de inicio


@app.route('/carrito')
def mostrar_carrito():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para ver tu carrito.', 'warning')
        return redirect(url_for('login'))

    id_cliente = session['id_cliente']
    cur = mysql.connection.cursor()

    # Consulta para obtener los productos del carrito del cliente
    cur.execute ("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s ", (id_cliente,))
    productos_carrito = cur.fetchall()

    carrito=[]
    total_carrito = 0
    for producto_carrito in productos_carrito:
        id_producto = producto_carrito[0]
        cantidad = producto_carrito[1]

        cur.execute ("SELECT id, nombre, precio FROM productos WHERE id = %s ", (id_producto,))
        producto = cur.fetchone()
        # Calcular el total del carrito
        if producto:
            total = producto[2] * cantidad  # precio * cantidad
            carrito.append({
                'id': producto[0],
                'nombre': producto[1],
                'precio': producto[2],
                'cantidad': cantidad,
                'total': total
            })
            total_carrito += total  # Sumar al total del carrito
    cur.close()
    print("Contenido del carrito:", carrito)

    return render_template('carrito.html', carrito=carrito, total_carrito=total_carrito, MONEDA=MONEDA)
    
@app.route('/carrito/agregar', methods=['POST'])
def agregar_producto_carrito():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para ver tu carrito.', 'warning')
        return redirect(url_for('login'))

    id_cliente = session['id_cliente']
    id_producto = request.form.get('id_producto')
    cantidad = request.form.get('cantidad', 1)

    cur = mysql.connection.cursor()

    # Verificar si el producto ya está en el carrito
    cur.execute("SELECT cantidad FROM carrito WHERE id_cliente = %s AND id_producto = %s", (id_cliente, id_producto))
    producto_en_carrito = cur.fetchone()

    if producto_en_carrito:
        # Si el producto ya está en el carrito, actualizamos la cantidad
        nueva_cantidad = producto_en_carrito[0] + int(cantidad)
        cur.execute("UPDATE carrito SET cantidad = %s WHERE id_cliente = %s AND id_producto = %s", (nueva_cantidad, id_cliente, id_producto))
    else:
        # Si el producto no está en el carrito, lo agregamos
        cur.execute("INSERT INTO carrito (id_cliente, id_producto, cantidad) VALUES (%s, %s, %s)", (id_cliente, id_producto, cantidad))

    mysql.connection.commit()
    cur.close()

    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('catalogo'))

@app.route('/carrito/eliminar/<int:id_producto>', methods=['POST'])
def eliminar_producto_carrito(id_producto):
    if 'logueado' not in session:
        flash('Debes iniciar sesión para modificar tu carrito.', 'warning')
        return redirect(url_for('login'))

    id_cliente = session['id_cliente']
    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM carrito WHERE id_cliente = %s AND id_producto = %s", (id_cliente, id_producto))
    mysql.connection.commit()
    cur.close()

    flash('Producto eliminado del carrito.', 'success')
    return redirect(url_for('mostrar_carrito'))


if __name__ == '__main__':
    app.run(debug=True)