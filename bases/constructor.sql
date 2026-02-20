CREATE TABLE locales_temp AS (SELECT * FROM locales);

DROP TABLE locales;

DROP TABLE centros_comerciales;

/*
-----------------------------------------------------------------------------------------------------------------
TABLA CENTROS_COMERCIALES - TABLA CENTROS_COMERCIALES - TABLA CENTROS_COMERCIALES - TABLA CENTROS_COMERCIALES 
-----------------------------------------------------------------------------------------------------------------
Igual que para la otra tabla este es el procedimiento de carga
*/

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
  parroquia VARCHAR[] NOT NULL,
  perimetro_calles VARCHAR[] NOT NULL,
  struct_contexto STRUCT(palabra VARCHAR, frecuencia INTEGER)[] NOT NULL,
);

/* 
-----------------------------------------------------------------------------------------------------------------
TABLA LOCALES - TABLA LOCALES - TABLA LOCALES - TABLA LOCALES - TABLA LOCALES - TABLA LOCALES -TABLA LOCALES
-----------------------------------------------------------------------------------------------------------------
Al ejecutar esto, creas la tabla local.
Para llenarla haz una temporal en el siguiente orden.
*/

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

/*
---------------------------------------------------------------------------------------------------------------------
 ACTUALIZAR TABLA CENTROS_COMERCIALES -  ACTUALIZAR TABLA CENTROS_COMERCIALES -  ACTUALIZAR TABLA CENTROS_COMERCIALES
--------------------------------------------------------------------------------------------------------------------
Paso final para tener tablas llenas.
*/

INSERT INTO centros_comerciales (
  SELECT 
    * EXCLUDE (parroquia, struct_contexto), 
    CAST(parroquia AS VARCHAR[]) AS parroquia, 
    CAST(struct_contexto AS STRUCT(palabra VARCHAR, frecuencia VARCHAR)[])  struct_contexto 
  FROM read_csv("centros_comerciales.psv", sep="|")
);

/*
-----------------------------------------------------------------------------------------------------------------
 ACTUALIZAR TABLA LOCALES -  ACTUALIZAR TABLA LOCALES -  ACTUALIZAR TABLA LOCALES -  ACTUALIZAR TABLA LOCALES 
-----------------------------------------------------------------------------------------------------------------
Paso final para tener tablas llenas.
*/
INSERT INTO locales (
  SELECT * FROM locales_temp
);
DROP TABLE locales_temp;
