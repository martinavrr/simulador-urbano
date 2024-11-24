# ZOrZiM
(data Zcience)-ORiented ZImulation of Mobility

## How to run

### Paso 1: Preparación

Si usas Windows, te recomiendo instalar el [Windows Subsystem for Linux](https://docs.microsoft.com/es-es/windows/wsl/install-win10). Puede ser la versión 1 o 2 (recomiendo WSL2). Como distribución te recomiendo Ubuntu 22.04 (es la que uso yo). 

Abre la consola (_shell_) de Ubuntu y ejecuta el siguiente comando:

```sh
sudo apt install make libxcursor1 libgdk-pixbuf2.0-dev libxdamage-dev osmctools gcc
```

Esto instalará algunas bibliotecas que son necesarias para el funcionamiento de `aves` (particularmente de `graph-tool` que es usada por aves).

Además, para administrar el entorno de ejecución de aves necesitas una instalación de `conda` ([Miniconda](https://docs.conda.io/en/latest/miniconda.html) es una buena alternativa) y de `mamba`. Primero debes instalar `conda`, y una vez que la tengas, puedes ejecutar:

```sh
conda install mamba
```

¿Por qué `mamba`? Es una versión más eficiente de `conda`. ¡Te ahorrará muchos minutos de instalación!


### Paso 2: Creación del Entorno

Después de descargar o clonar el repositorio (utilizando el comando `git clone`), debes instalar el entorno de `conda` con los siguientes comandos:

```sh
make conda-create-env
make install-package
```

Ello creará un entorno llamado `zorzim` que puedes utilizar a través del comando `conda activate zorzim`.

```sh
conda activate zorzim
```

Para descargar los datos de OpenStreetMap puedes ejecutar:

```
make download-external
```
Lo que descargará algunos archivos `.pbf` para ejecutar con el simulador, en particular el archivo `chile-rm-latest.pbf`.

Luego, puedes ejecutar la simulación con:

```bash
python scripts/run.py --pbf chile-rm-latest
```

Abre [http://127.0.0.1:8521/](http://127.0.0.1:8521/) en tu navegador y haz click en `Start`.

### Paso 3: Ejecución en Jupyter

Es posible que ya tengas un entorno de `conda` en el que ejecutes Jupyter. En ese caso, puedes agregar el entorno de `zorzim` como _kernel_ ejecutando este comando desde el entorno que contiene Jupyter:

```sh
make install-kernel
```

Así quedará habilitado acceder al entorno de zorzim desde Jupyter.


## Actualización de Dependencias

Para añadir o actualizar dependencias:

1. Agrega el nombre (y la versión si es necesaria) a la lista en `environment.yml`.
2. Ejecuta `conda env update --name zorzim --file environment.yml  --prune`.
3. Actualiza el archivo `environment.lock.yml` ejecutando `conda env export > environment.lock.yml`.
