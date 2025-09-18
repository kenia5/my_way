import requests #realiza solicitudes HTTP 

from flask import Flask, render_template, redirect, session, abort
from functools import wraps
import sqlite3


def bug(message, code=400):
  abort(code, message)

def get_db_connection():
  #Guardar la conexion en una variable
  db = sqlite3.connect("way.db")
  #Devolver el resukltado de la consulta
  db.row_factory = sqlite3.Row
  return db

def delete_item(item_type, item_id):
  db = get_db_connection()
  cursor = db.cursor()
  try:
    if item_type == "goal":
      cursor.execute("DELETE FROM goals WHERE id = ?", (item_id,))
    elif item_type == "project":
      cursor.execute("DELETE FROM projects WHERE id = ?", (item_id,))
    elif item_type == "task":
      cursor.execute("DELETE FROM tasks WHERE id = ?", (item_id,))
    else:
      return
    
    db.commit()

  except Exception as e:
    print(f"Error al eliminar elemento: {e}")
    return 
  finally:
    db.close()