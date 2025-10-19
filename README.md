# Genome Annotation Viewer (PyQt5 + Matplotlib + Biopython)

Visor interactivo de anotaciones genómicas desde archivos **GenBank** con capacidades de edición básica.

## Características
- Panel de bienvenida con guía rápida y resumen del genoma cargado (ID, longitud, topología, ruta del archivo).
- Barra de herramientas con accesos directos para abrir/guardar, añadir/eliminar y controlar el zoom.
- Canvas interactivo con zoom dinámico (botones + rueda), desplazamiento fluido y resaltado de la anotación seleccionada.
- Buscador instantáneo de anotaciones + tabla editable sincronizada con el visor.
- Editor dedicado de *features* para modificar tipo, rango, orientación y metadatos con validación básica.
- Añadir/eliminar *features* manualmente y exportar manteniendo el formato GenBank.
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
- **Zoom:** botones `Zoom +`, `Zoom −`, rueda del mouse o gesto de pinza (trackpad).
- **Pan:** click y arrastrar con el botón izquierdo.
- **Vista completa:** botón `Ver todo` de la barra superior o `home` de la toolbar de matplotlib.

### Edición
- Selecciona una anotación y usa el panel inferior para modificar tipo, inicio, fin, orientación y metadatos (`clave=valor; ...`).
- También puedes editar directamente en la tabla si prefieres la vista tabular.
- Botones **Añadir característica** y **Eliminar característica** para gestionar anotaciones rápidamente.
- **Save** guardará en el mismo archivo; **Save As...** abrirá diálogo.

> Nota: El ejemplo usa un pequeño *plásmido ficticio* para demostración.
