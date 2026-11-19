# KeePass LAN Share — prototipo Windows

Transfiere una contraseña copiada desde KeePassXC al portapapeles de otro PC Windows de la misma LAN, tras selección explícita y aprobación del destinatario.

## Instalación en ambos ordenadores

1. Descomprimir esta carpeta en cada ordenador Windows.
2. Ejecutar **`start.bat`** con doble clic. No hace falta instalar Python ni uv manualmente.
3. Si `uv` no existe, el primer inicio descarga su instalador oficial y lo guarda **solo en `.tools\uv`**; no modifica el `PATH`. Si ya existe `uv` en el sistema lo reutiliza.
4. `uv sync` descarga Python 3.12 si hace falta, crea `.venv` automáticamente y sincroniza las dependencias. En inicios posteriores, reutiliza el entorno. **La primera ejecución necesita Internet** y acceso a `astral.sh`, GitHub (descargas) y al índice de paquetes, salvo que ya estén en caché.
5. Cuando Windows Defender Firewall pregunte, permitir la aplicación **solo en redes privadas autorizadas**. Si no aparece una solicitud, gestionar la regla de entrada para **TCP 43187** en el perfil **Privado**. El descubrimiento usa mDNS **UDP 5353**, que también debe permitirse en los equipos afectados. No habilitar reglas en redes públicas.
6. En ambos equipos debe aparecer el otro en el desplegable. Si no aparece, comprobar que estén en la misma LAN y que la red no bloquee multicast/mDNS, las interfaces IPv4 anunciadas o los puertos anteriores.

## Inicio automatico con uv

- `start.bat`: unico archivo que necesitas abrir. Llama a `bootstrap.ps1`.
- `bootstrap.ps1`: detecta `uv`, lo instala localmente si falta y ejecuta `uv sync --python 3.12` antes de iniciar la interfaz.
- `pyproject.toml` y `.python-version`: fijan dependencias y Python 3.12.
- `uv.lock`: cuando se genera, permite instalaciones reproducibles (mantenerlo con el proyecto).
- `.venv/` y `.tools/`: carpetas locales creadas automaticamente, no compartirlas al distribuir el proyecto.

Si las politicas de seguridad de la empresa bloquean la descarga o ejecucion del instalador oficial de uv, TI debe instalar `uv` de forma autorizada. El primer inicio **descarga y ejecuta un instalador remoto**, por lo que conviene aprobar ese paso antes de distribuirlo en una red corporativa. Una vez preparado el entorno, puede funcionar sin Internet mientras la LAN este disponible.

## Uso

1. En KeePassXC, seleccionar una entrada y pulsar **Ctrl+Alt+S** (copia la contraseña y la registra). Copias hechas a mano no se envían.
2. En KeePass LAN Share, elegir el destinatario y pulsar «Enviar contraseña copiada». Si el portapapeles ha cambiado desde Ctrl+Alt+S, el envío se cancela. El contenido nunca se muestra en la ventana.
3. La **primera vez**, ambos ordenadores muestran un código de 8 dígitos: verificarlo **verbalmente o presencialmente**, no a través del propio canal no autenticado. Ambos deben confirmar.
4. En el equipo receptor, aceptar la solicitud de envío. La contraseña pasa a su portapapeles durante un máximo de 20 segundos; pegar con Ctrl+V.
5. En próximos envíos entre equipos emparejados, se mantiene la verificación criptográfica del dispositivo; siempre se exige aceptación de cada contraseña.

## Mecanismos de seguridad

- **Sin conexión a KeePassXC ni acceso a su base .kdbx**: solo lee el portapapeles al pulsar «Enviar».
- **Descubrimiento local:** mDNS/zeroconf. Los anuncios no contienen secretos. No garantiza por sí solo identidad; la autenticación se hace mediante claves.
- **Autenticación:** identidad Ed25519 guardada mediante `keyring` en el Administrador de credenciales de Windows. Primera vinculación con **SAS de 8 dígitos** validado por las dos personas; en posteriores conexiones, claves públicas conocidas.
- **Cifrado de extremo a extremo:** claves efímeras X25519, firmas Ed25519 sobre el intercambio, HKDF-SHA256 y AES-256-GCM con secuencias y claves de envío/recepción separadas.
- **Aceptación explícita del receptor** antes de que se transmita la contraseña.
- **Sin historial ni registros de secretos por diseño**. Se guardan solo identificadores públicos de equipos autorizados en `%LOCALAPPDATA%\KeePassLANShare\peers.json`.
- **El portapapeles se borra a los 20 segundos** si sigue conteniendo la misma contraseña. Se añaden formatos de exclusión del historial/cloud de Windows; la efectividad puede depender de las aplicaciones que observan el portapapeles.

## Limitaciones importantes

**Prototipo para pruebas internas, no un producto de seguridad auditado.** No lo implantes para secretos de alta criticidad sin revisión de seguridad, pruebas de penetración y validación con el departamento TI.

- El destinatario puede copiar, capturar o guardar la contraseña una vez recibida. Una revocación real requiere cambiar la credencial del dispositivo o dar cuentas separadas.
- El portapapeles puede ser leído por software local con los permisos adecuados. No es una alternativa a la gestión de accesos privilegiados.
- Los nombres de equipo y las direcciones IP no son fiables como comprobación de identidad; verificar siempre el código del emparejamiento presencialmente o por un canal autenticado distinto.
- Si se ejecuta en un ordenador comprometido, el cifrado de red no protege el contenido en ese equipo.
- La memoria de Python/Qt no permite garantizar borrado criptográfico del secreto en RAM.
- El equipo receptor debe tener la aplicación en ejecución, sesión gráfica disponible y permitir conexiones TCP de entrada.
- Una red corporativa puede bloquear mDNS o conexiones entre estaciones aunque pertenezcan a la misma subred.
- No hay gestión centralizada de equipos ni política corporativa; el almacén de confianza es local a cada usuario Windows.
- Si KeePassXC borra antes el portapapeles, hay que volver a copiar la contraseña antes de pulsar enviar.

## Ejecutable Windows

Ejecutar `build-exe.bat` en **Windows**. Genera `dist\KeePassLANShare\KeePassLANShare.exe`. Copiar **toda la carpeta** `dist\KeePassLANShare` al equipo de destino (el ejecutable no es autónomo fuera de esa carpeta). Verificar y firmar el binario según las políticas de TI.

## Pruebas de protocolo

Con el entorno creado por `start.bat`, ejecutar:

`uv run --no-sync python -m unittest discover -s tests -v`

Las pruebas automáticas de protocolo no sustituyen las pruebas reales en dos equipos Windows ni la auditoría criptográfica.

## Versión 0.2: aplicación residente, atajo e instalador

### Instalación del ejecutable en Windows

Para generar el instalador en una máquina **Windows**:

1. Instala [Inno Setup 6](https://jrsoftware.org/isinfo.php) (herramienta de compilación del instalador). El proyecto también necesita acceso inicial a Internet para que `uv` descargue Python y las dependencias.
2. Ejecuta `build-installer.bat`. Este invoca `build-exe.bat` (PyInstaller), después compila `installer.iss` con Inno Setup.
3. El archivo distribuible estará en `installer-output\KeePassLANShare-Setup.exe`. **No es necesario instalar Python ni uv en los ordenadores de destino**.
4. Ejecuta el instalador con el usuario Windows que utilizará la aplicación; no requiere permisos de administrador para instalarse en el perfil de usuario.
5. Deja marcada la tarea «Iniciar automáticamente con Windows» si quieres que se ejecute al iniciar sesión. Desde la ventana también podrás habilitar o deshabilitar el arranque automático.
6. Para recibir transferencias, permitir la comunicación de red entrante TCP 43187 en el perfil Privado. En ordenadores corporativos podría requerirse una regla administrada por TI. El descubrimiento utiliza mDNS UDP 5353. **No es recomendable abrir esos puertos en redes públicas**.

**Importante:** Linux no puede generar ni probar aquí un instalador Windows de manera fiable. Los scripts y el `.iss` están listos, pero deberán compilarse y probarse en Windows.

### Uso del atajo

1. Abre KeePassXC y desbloquea tu base de datos.
2. Selecciona la entrada que contiene la contraseña (sin abrir el editor de la entrada).
3. Con KeePassXC en primer plano, pulsa `Ctrl+Alt+S` y suelta las teclas.
4. La aplicación comprueba que la ventana activa pertenece al proceso `KeePassXC.exe`, envía `Ctrl+C` a dicha ventana y comprueba si se ha actualizado el portapapeles.
5. Si KeePassXC ha copiado texto nuevo, se muestra la ventana de KeePass LAN Share. Selecciona el destinatario y pulsa «Enviar».
6. El compañero confirma la recepción y pega la contraseña en su dispositivo.

Si el atajo está ocupado por otra aplicación, habrá un aviso. Si KeePassXC no tiene una entrada seleccionada, la ventana no se abrirá. El atajo **no lee el almacén de KeePassXC**, únicamente automatiza la operación de copiar contraseña. El botón de envío continúa solicitando confirmación explícita del destinatario.

### Bandeja del sistema y cierre

- Cerrar la ventana con la X únicamente la oculta; la aplicación sigue funcionando en segundo plano.
- Doble clic en el icono de bandeja: abre la ventana.
- Menú del icono > «Salir»: libera el puerto, detiene el atajo y finaliza el proceso.
- Una sesión de Windows iniciada es necesaria para leer y escribir el portapapeles: **el arranque es al iniciar sesión, no antes de que el usuario entre**.
- El inicio automático se configura mediante la clave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, sin credenciales de administrador.

### Limitaciones de seguridad del atajo

El atajo comprueba el **nombre del ejecutable activo**, no valida la firma del proceso. No sustituye a la comprobación manual de qué entrada está seleccionada. Si el campo de texto que tiene el foco en KeePassXC intercepta `Ctrl+C`, podría copiar otro texto. **Comprueba siempre la entrada seleccionada antes de pulsar el atajo y confirma el destinatario**.

Los controles del portapapeles y el cifrado siguen sujetos a las limitaciones descritas anteriormente. La versión 0.2 es un **prototipo no auditado** y requiere validación con dos PCs Windows antes de utilizarse con contraseñas de producción.
