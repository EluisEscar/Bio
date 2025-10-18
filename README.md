# Genome Annotation Viewer (PyQt5 + Matplotlib + Biopython)

Visor interactivo de anotaciones genómicas desde archivos **GenBank** con capacidades de edición básica.

## Características
- Carga y visualización de genomas (secuencia lineal) y sus *features*.
- Canvas interactivo con **zoom** (rueda del mouse) y **pan** (arrastrar con botón izquierdo).
- Tabla editable para modificar tipo, inicio, fin, hebra y *qualifiers*.
- Añadir/eliminar *features* manualmente.
- Exportar a GenBank (sobrescribe o "Guardar como...").
- **Patrón Observer** simple mediante un *EventBus* para desacoplar Modelo/Views.

## Requisitos
- Python 3.8+
- PyQt5
- Biopython
- matplotlib

```
pip install -r requirements.txt
```

## Uso
```
python main.py
```
Se cargará automáticamente un ejemplo (`data/example.gb`). También puedes abrir otro archivo GenBank desde **File → Open...**.

### Controles del canvas
- **Zoom:** rueda del mouse.
- **Pan:** click y arrastrar con el botón izquierdo.
- **Reset:** botón "home" de la toolbar de matplotlib.

### Edición
- En la tabla puedes editar celdas: `type`, `start`, `end`, `strand`, `qualifiers` (como `key1=val1; key2=val2`).  
- Botón **Add Feature** para añadir una anotación; **Delete Feature** para eliminar la fila seleccionada.
- **Save** guardará en el mismo archivo; **Save As...** abrirá diálogo.

> Nota: El ejemplo usa un pequeño *plásmido ficticio* para demostración.
