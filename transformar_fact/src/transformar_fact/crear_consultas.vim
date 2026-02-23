" Script para generar y mostrar queries SQL con saltos de línea
for y in range(2025, 2025)
  for m in range(1, 12)

    let lineas = [
          \ 'SELECT',
          \ '  CAST(clave_acceso AS CHAR) AS clave_acceso,',
          \ '  dia,',
          \ '  mes,',
          \ '  anio,',
          \ '  numero_comprobante,',
          \ '  codigo_establecimiento,',
          \ '  tipo_id_comprador,',
          \ '  id_comprador,',
          \ '  CAST(id_establecimiento AS CHAR) AS id_establecimiento,',
          \ '  CAST(ruc_vendedor AS CHAR) AS ruc_vendedor,',
          \ '  CAST(total AS FLOAT) AS total',
          \ 'FROM df_data_general_facturas_' . y . '_' . printf("%02d", m),
          \ '  WHERE id_establecimiento IN ({rucs_a_buscar});',
          \ ''
          \ ]

    put = lineas

  endfor
endfor

