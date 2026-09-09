# updt-propio

Módulos propios para montar como submódulo en proyectos de Odoo.sh.

## Ramas

Una por versión de Odoo. Cada módulo va en la rama que le corresponde.

| Rama | Para |
|---|---|
| `main` | Solo esta documentación. No la uses como submódulo. |
| `16.0` | Módulos de Odoo 16 |
| `17.0` | Módulos de Odoo 17 |
| `18.0` | Módulos de Odoo 18 |
| `19.0` | Módulos de Odoo 19 |

**La versión del `__manifest__.py` tiene que empezar por la de la rama.** Si
subes un módulo `18.0.1.0.0` a un proyecto de Odoo 19, Odoo lo descarta al
arrancar con este aviso y no aparece siquiera en Aplicaciones:

```
The module <nombre> has an incompatible version, setting installable=False
```

## Cómo subir un módulo

```bash
git clone https://github.com/wascar-chai/updt-propio.git
cd updt-propio
git checkout 19.0                 # la rama de la versión que toque

cp -r /ruta/de/mi_modulo .        # o descomprime el zip aquí

git add mi_modulo
git commit -m "[ADD] mi_modulo: qué hace"
git push origin 19.0
```

Antes de subir, tres comprobaciones que ahorran disgustos:

```bash
# 1. La versión del manifest coincide con la rama
grep '"version"' mi_modulo/__manifest__.py

# 2. El Python compila
python -m compileall -q mi_modulo

# 3. No se cuela ningún __pycache__ ni credenciales
git status --short
grep -rniE "ghp_|password|token|secret" mi_modulo/
```

El `.gitignore` ya excluye `__pycache__/` y los `.pyc`.

## Conectarlo a Odoo.sh

En **Settings → Submodules → Add module** del proyecto:

1. **Git repository:** `git@github.com:wascar-chai/updt-propio.git`
2. **Branch:** la de la versión del proyecto (`17.0`, `18.0` o `19.0`)

Odoo.sh lee el repositorio por SSH con su propia clave de despliegue. Si el
repositorio es privado, hay que autorizarla primero:

1. Copia la clave pública que muestra Odoo.sh en *Settings → Submodules*.
2. En GitHub: repositorio → **Settings → Deploy keys → Add deploy key**.
3. Pégala. Con acceso de solo lectura basta.

Sin ese paso el desplegable de ramas se queda vacío o falla al clonar.
