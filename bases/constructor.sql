CREATE TABLE locales (
  local_CC VARCHAR(120) CHECK(local_CC = lower(local_CC)),
  centro_comercial VARCHAR(80) CHECK(
    centro_comercial IN (
      'Paseo Shopping', 
      'El Jardin', 
      'Mall del Sol', 
      'Quicentro', 
      'Portal Shopping', 
      'San Marino', 
      'Recreo', 
      'Mall de los Andes', 
      'Mall del Pacifico', 
      'Paseo San Francisco', 
      'Condado Shopping', 
      'Scala Shopping'
    )
  ),
  categoria VARCHAR(70) CHECK(
    categoria IN (
      'mascotas', 
      'vehiculos', 
      'servicios', 
      'accesorios', 
      'zona-bancaria', 
      'entretenimiento', 
      'gastronomia', 
      'salud-y-belleza', 
      'electrodomesticos-y-tecnologia', 
      'moda', 
      'supermercados-y-ferreterias'
      )
    ),
  PRIMARY KEY (local_CC, centro_comercial),
  FOREIGN KEY (centro_comercial) REFERENCES centros_comerciales(centro_comercial)
  );

CREATE TABLE centros_comerciales (
  centro_comercial VARCHAR(100) CHECK(
    centro_comercial IN (
      'Paseo Shopping', 
      'El Jardin', 
      'Mall del Sol', 
      'Quicentro', 
      'Portal Shopping', 
      'San Marino', 
      'Recreo', 
      'Mall de los Andes', 
      'Mall del Pacifico', 
      'Paseo San Francisco', 
      'Condado Shopping', 
      'Scala Shopping'    
    )
  ) PRIMARY KEY,
  provincia VARCHAR(40) CHECK(
    provincia in (
      'galapagos', 
      'azuay', 
      'bolivar', 
      'cañar',
      'carchi',
      'chimborazo',
      'cotopaxi',
      'el oro',
      'esmeraldas',
      'guayas',
      'imbabura',
      'loja',
      'los rios',
      'manabi',
      'morona santiago',
      'napo',
      'orellana',
      'pastaza',
      'pichincha',
      'santa elena',
      'santo domingo de los tsachilas',
      'sucumbios',
      'tungurahua',
      'zamora chinchipe'
    )
  ) NOT NULL,
  canton VARCHAR(30) CHECK(
    canton NOT LIKE '%,%'
    and canton = lower(canton)
  ) NOT NULL,
  parroquia VARCHAR(200) CHECK(
    regexp_full_match(parroquia, '^[a-z0-9 ,]+$')
    and parroquia = lower(parroquia)
  ) NOT NULL,
  perimetro_calles VARCHAR(800) CHECK(
    regexp_full_match(perimetro_calles, '^[a-z0-9 ,]+$')
    and perimetro_calles = lower(perimetro_calles)
  ) NOT NULL,
);

INSERT INTO centros_comerciales (centro_comercial, provincia, canton, parroquia, perimetro_calles)
(
  SELECT
    centro_comercial, provincia, canton, parroquia, perimetro_calles
  FROM (
    SELECT 
      centro_comercial,
      provincia,
      canton,
      parroquia,
      perimetro_calles,
      CASE 
        WHEN regexp_split_to_array(parroquia, ',') = list_transform(
          regexp_split_to_array(parroquia, ','),
          lambda x: regexp_replace(regexp_replace(x, '^ +| +$', ''), ' +', ' ')
        ) THEN TRUE
        ELSE FALSE
      END AS constrain_parroquia,
      CASE 
        WHEN regexp_split_to_array(perimetro_calles, ',') = list_transform(
          regexp_split_to_array(perimetro_calles, ','),
          lambda x: regexp_replace(regexp_replace(x, '^ +| +$', ''), ' +', ' ')
        ) THEN TRUE
        ELSE FALSE
      END AS constrain_perimetro_calles
    FROM read_csv('centros_comerciales.psv', sep='|')
    WHERE constrain_parroquia IS NOT FALSE AND constrain_perimetro_calles IS NOT FALSE
  )
);
