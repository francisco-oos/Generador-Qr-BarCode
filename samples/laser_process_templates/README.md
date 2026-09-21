# Plantillas de proceso láser v0.10 experimental

Estas plantillas contienen **sólo geometría**. No incluyen velocidad, potencia ni pasadas.

- `line_engrave_card.svg`: grabado vectorial de línea.
- `fill_engrave_patch.svg`: contorno cerrado que Marking Studio convierte a hatch usando `interval_mm` del preset validado.
- `cut_geometry_coupon.svg`: repetibilidad de corte geométrico.
- `cut_papercut_panel.svg`: panel simple de papel picado para pruebas sacrificiales.

Para control directo, la geometría se compila junto con un preset local marcado como validado en la **misma máquina y superficie**, se ejecuta Frame con M5 y sólo después puede habilitarse Start.

Estos archivos no son recetas universales de material.
