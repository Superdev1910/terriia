"""Datos para la pantalla "Delegaciones Municipales".

Solo parte visual: los datos viven aquí en una lista, sin base de datos ni validaciones.
Cada delegación es un diccionario; la plantilla recorre la lista y dibuja una tarjeta por cada una.
"""

# Coordenadas aproximadas. Para afinarlas: en Google Maps, clic derecho sobre el lugar
# y copiar los dos números (latitud, longitud).
CENTRO_LA_SERENA = (-29.9027, -71.2519)

DELEGACIONES = [
    {
        "codigo": "companias",
        "nombre": "Las Compañías",
        "encargado": "Carlos E. Rojas Poblete",
        "direccion": "Esmeralda 2422, Costado Banco Estado",
        "correo": "lascompanias@laserena.cl",
        "telefonos": "512 206527 | +569 57716495",
        "lat": -29.8830,
        "lng": -71.2200,
        "informacion": [
            "Por el sostenido crecimiento que ha experimentado el sector de Las Compañías en el curso de los últimos años, ha sido necesaria la presencia permanente de la Municipalidad de La Serena a través de la Delegación Municipal de Las Compañías en contexto de Centro Cívico.",
            "La Delegación Municipal de Las Compañías se compone de 21 funcionarios, cuyo principal objetivo es el contacto directo con la comunidad residente. A través de su gestión, la Municipalidad de La Serena busca fortalecer los lazos con las personas, familias, organizaciones comunitarias, territoriales y de base, e integrarlas efectivamente al desarrollo económico y social presente en la Comuna.",
            "Para ello, la Delegación Municipal de Las Compañías se ha transformado no solo en un punto de encuentro de la comunidad, sino, además, gestor de iniciativas de apoyo a las familias del sector en distintos ámbitos del desarrollo social.",
            "Junto con lo anterior, la Ilustre Municipalidad de La Serena, ha generado convenios con otras entidades con objeto de ofrecer a la comunidad de Las Compañías acceso de servicios básicos, evitando con ello el desplazamiento de su población a la ciudad de La Serena.",
            "Existen convenios con Fonasa. Registro Civil y Registro Social de Hogares, con los cuales, además, se cuenta con los Tótems de Autoatención, optimizando ostensiblemente el servicio comunitario.",
            "Otro Convenio con muy buenos resultados en su desarrollo general, es el Convenio de Trabajos Comunitarios con la Unidad CRS. Gendarmería, que permite el cumplimiento de penas mínimas para trabajos comunitarios en el territorio. (Convenio suspendido en ejecución por Pandemia Covid19 y disponible a partir de Fase 4.)",
            "El crecimiento demográfico de la población del territorio, ha provocado una importante demanda de servicios municipales producto de la Pandemia Covid19. Para ello, se crean mecanismos de apoyo virtual y presencial especialmente en las Plataformas Ciudadanas, incrementando notoriamente dichos procesos para “acercar el trámite” a una comunidad altamente vulnerable.",
            "Desde al Año 2020, se inaugura el servicio paralelo denominado: Subdelegación Las Compañías (Sector Plaza San Bartolomé – Calle Alejandro Flores S/N. Entre Colombia y Ecuador) como una forma de incrementar y mejorar el servicio comunitario general en el territorio para la alta demanda demográfica del sector. Por tal razón, se divide el equipo de funcionarios de unidades fundamentales para reforzar el servicio de la municipalidad, entre las unidades que prestan apoyo permanente en el sector son:",
        ],
        "unidades": [
            "Planificación. Control de Gestión y Administrativa: Atención de Público, Subsidios y Plataformas.",
            "Social.",
            "Adulto Mayor.",
            "DISERCO.",
            "Territorio y Organizaciones Comunitarias.",
            "Género y Equidad de Género",
            "Registro Social de hogares (Apoyo Plataforma Ciudadana).",
        ],
    },
    # Las coordenadas de las demás delegaciones son APROXIMADAS: afínalas con Google Maps
    # (clic derecho sobre el lugar exacto y copiar los dos números).
    {
        "codigo": "pampa",
        "nombre": "La Pampa",
        "encargado": "María Soledad Rojas",
        "direccion": "Larraín Alcalde 3505 esquina 4 Esquinas",
        "correo": "pampa@laserena.cl",
        "telefonos": "512 206788 | +569 47189803",
        "lat": -29.9335,  # aproximada, afinar
        "lng": -71.2330,
        "informacion": [
            "La Ilustre Municipalidad de La Serena, en el contexto de mejorar la gestión en los territorios, crea el año 2012 la Delegación La Pampa, teniendo como límites territoriales: al norte Amunátegui, al sur Regimiento Arica, al oeste Ruta 5 y al este Cerro Grande / Huachalalume.",
            "Su funcionamiento se divide en tres áreas:",
        ],
        "unidades": [
            "Área social: proporciona orientación y atención de casos sociales, además de la tramitación de subsidios familiares, maternales, agua potable y exención del cobro de la basura, entre otros.",
            "Área organizaciones comunitarias y participación ciudadana: asesora a las organizaciones comunitarias territoriales y funcionales del sector, en base a la ley 19.418 y 20.500. Promueve en el territorio una cultura cívica y actividades que fomenten la participación vecinal.",
            "Área servicio a la comunidad: fiscaliza y/o mantiene áreas verdes no concesionadas del territorio, deriva y realiza seguimiento de casos de mantención de aseo y ornato, alumbrado público y medio ambiente, pertenecientes a la dirección de servicio a la comunidad.",
            "Actividades relevantes: Pinta Tu Barrio, Invierno Solidario, Cine En Tu Barrio y Mejora Tu Plaza.",
        ],
    },
    {
        "codigo": "antena",
        "nombre": "La Antena - La Florida",
        "encargado": "Elizabeth Villanueva Oyarce",
        "direccion": "18 de Septiembre esquina Emilio Bello",
        "correo": "antena@laserena.cl",
        "telefonos": "512 206618 | +569 57723998",
        "lat": -29.9190,  # aproximada, afinar
        "lng": -71.2070,
        "informacion": [
            "La Delegación Municipal de La Antena es un ente representante de la Ilustre Municipalidad de La Serena en el territorio. Cuenta con catorce funcionarios que coordinan y armonizan los esfuerzos del Municipio, para canalizar inquietudes y problemáticas realizadas por la comunidad, de esta manera se establecen vías más directas de acercamiento de los vecinos y las organizaciones con la Primera Autoridad Comunal.",
            "Es deber de la Delegación Municipal de La Antena promover el desarrollo del territorio La Antena, La Florida, Ceres y Alfalfares a través de políticas públicas comunales, en materia de servicio a la comunidad, desarrollo comunitario, seguridad ciudadana, social, cultural y deportiva con identidad ambiental, para mejorar la calidad de vida de todos sus habitantes.",
            "Finalmente, la Delegación Municipal de La Antena se transforma en un punto de encuentro de la comunidad, ubicado en el corazón del sector alto de nuestra comuna, además de crear instancias de apoyo a las familias de los sectores cercanos en distintos ámbitos del desarrollo social, deportivo, medioambiental y cultural.",
        ],
        "unidades": [],
    },
    {
        "codigo": "avdelmar",
        "nombre": "Av. del Mar",
        "encargado": "Rodrigo Fuenzalida Vásquez",
        "direccion": "Avenida del Mar 2500 esquina Florencio Sánchez",
        "correo": "avenidadelmar@laserena.cl",
        "telefonos": "512 206518 | +569 57717448",
        "lat": -29.9265,  # aproximada, afinar
        "lng": -71.2765,
        "informacion": [
            "Esta Delegación está abocada a dar apoyo a los vecinos del territorio, trabajando conjuntamente con las organizaciones territoriales y funcionales del sector. Así mismo, el funcionamiento de esta unidad se sustenta principalmente en la articulación de las líneas de intervención municipal, teniendo como foco el poder cubrir de mejor forma las necesidades de la comunidad.",
            "Por otra parte, se presta apoyo a toda aquella actividad derivada de otros servicios gubernamentales, municipales y privados que van dirigidos a la comunidad. Destacando entre ellos aquellos orientados a mantener y resguardar la Seguridad Ciudadana y el Medio Ambiente. De esta forma, se coordinan acciones para cuidar el terreno playa y el Bien Nacional de Uso Público del sector de la Avenida del Mar, siendo responsable del equipo de rescate en temporada estival, y coordinando e informando a los vecinos para prepararlos ante emergencias, tales como terremotos y tsunamis, asesorando a los Administradores de Edificios en dicha materia.",
        ],
        "unidades": [],
    },
    {
        "codigo": "rural",
        "nombre": "Rural",
        "encargado": "Manuel Barraza Delgado",
        "direccion": "Carrera 281 esquina Brasil",
        "correo": "rural@laserena.cl",
        "telefonos": "512 206687 | +569 7420874",
        "lat": -29.9060,  # aproximada, afinar
        "lng": -71.2490,
        "informacion": [
            "En virtud que la extensión territorial comunal de La Serena corresponde al 93% de superficie rural, el municipio cuenta con la Delegación Rural con el objetivo de descentralizar y acortar la brecha entre las autoridades municipales, articular los diversos servicios municipales en base a las necesidades de la comunidad, y ser nexo entre la comunidad y servicios públicos, entidades privadas y Estado.",
            "Nuestro equipo consiste en 7 funcionarios que se despliegan en el territorio con el objetivo de cubrir las diversas necesidades con respecto a las áreas de intervención para el apoyo y asesoría a la comunidad rural:",
        ],
        "unidades": [
            "Área de gestión y planificación (512 206653): apoya y gestiona las acciones de la Delegación para su funcionamiento, trabajando en forma coordinada con la unidad del Administrador Municipal, Secretaría de Planificación y Gabinete en cuanto al diseño y ejecución de la Planificación Anual Operativa, Presupuesto Municipal y Reportes Mensuales, entre otros.",
            "Gestor de organizaciones comunitarias y participación ciudadana (512 427820): en base a la Ley 19.418 y 20.500, orienta y apoya a las organizaciones comunitarias territoriales y funcionales del territorio, en coordinación con la Oficina de Organizaciones Comunitarias y Participación Ciudadana (OCPC) de la DIDECO. Promueve y apoya actividades culturales, deportivas y de recreación, y operativos con servicios, entre otras.",
            "Gestor social (512 427841): profesional a cargo de asistir y generar alianzas de apoyo a las necesidades sociales de familias vulnerables del territorio. Orienta y apoya en la tramitación de subsidios estatales como Familiares, Maternales, Madre, Agua Potable, entre otros.",
            "Orientación jurídica (agendar hora al 512 206687): se cuenta con los servicios de una abogada una vez por semana que orienta a casos sociales sobre diversos problemas jurídicos en forma gratuita a toda la comunidad.",
            "Gestor de servicio a la comunidad (512 206604): lleva una planificación en base a requerimientos de la comunidad y levantamiento en terreno de necesidades del territorio. Articula y gestiona con el departamento municipal de servicio a la comunidad el mejoramiento y mantención de caminos de uso público de responsabilidad municipal, el retiro de basura domiciliaria, el seguimiento del alumbrado público, y coordina tolvas y cuadrillas de aseo para mantener el orden y la limpieza en áreas comunes y espacios públicos del territorio rural.",
            "Gestor de proyectos (512 206653): asesora a las organizaciones sociales del territorio en una, más o todas las fases de proyectos (elaboración, presentación, postulación, ejecución, seguimiento y rendiciones). Asesora a personas en proyectos de microemprendimiento y trabaja junto a SECPLAN en proyectos de inversión territorial rural.",
            "Gestor de adquisiciones (512 206653): levanta los requerimientos de insumos necesarios ante la sección de Adquisiciones para el normal funcionamiento de la Delegación. Además tramita solicitudes para actividades de auspicio, requerimientos de la comunidad y organizaciones, eventos y actividades rurales autorizadas.",
            "Gestor administrativo (512 206687): deriva las solicitudes recibidas por atención directa, radial y telefónica, y es ente de información y apoyo para una fluida comunicación entre la comunidad y la delegación. Responsable del orden administrativo interno y apoyo a los gestores. Además orienta a la comunidad interesada en participar de los programas y subsidios del SERVIU.",
        ],
    },
    {
        "codigo": "centro",
        "nombre": "Centro",
        "encargado": "Alan Von Kretschmann",
        "direccion": "Cienfuegos 226 esquina Colón",
        "correo": "centro@laserena.cl",
        "telefonos": "512 207861 | +569 57703917",
        "lat": -29.9035,  # aproximada, afinar
        "lng": -71.2530,
        "informacion": [
            "La Delegación Centro cuenta con las siguientes áreas de trabajo:",
        ],
        "unidades": [
            "Área social: orientación y atención de casos sociales, apoyo en la tramitación de beneficios y derivación a programas municipales.",
            "Área de organizaciones comunitarias y participación ciudadana: asesoría a organizaciones territoriales y funcionales, fortalecimiento de la participación vecinal y apoyo en la gestión comunitaria.",
            "Área de servicio a la comunidad: recepción y seguimiento de requerimientos relacionados con aseo, ornato, áreas verdes, alumbrado público y otras materias vinculadas a servicios comunitarios.",
            "Área de patrimonio: promoción, difusión y puesta en valor del patrimonio cultural e histórico del territorio, fortaleciendo la identidad local.",
            "Área administrativa: apoyo en la gestión interna de la delegación, atención de público y coordinación de servicios para una atención eficiente a la comunidad.",
        ],
    },
]
