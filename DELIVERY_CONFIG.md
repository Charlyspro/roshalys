# Configuración de Entregas por Producto

## Descripción

La funcionalidad **ProductDeliveryConfig** permite configurar opciones de entrega específicas para cada producto. Esto es útil para tiendas que tienen productos que no pueden ser enviados a domicilio (por ejemplo, productos voluminosos, frágiles o con restricciones especiales) o que tienen requisitos mínimos de cantidad para el envío.

## Modelo: ProductDeliveryConfig

```python
class ProductDeliveryConfig(models.Model):
    product = OneToOneField(Product)                     # Producto asociado
    allow_delivery = BooleanField(default=True)         # ¿Permitir envío a domicilio?
    min_quantity_for_delivery = IntegerField(default=1) # Cantidad mínima para envío
```

### Campos

| Campo | Tipo | Por defecto | Descripción |
|-------|------|------------|-------------|
| `product` | OneToOneField | - | Referencia única al producto |
| `allow_delivery` | Boolean | True | Si es False, el producto solo se puede recoger en local |
| `min_quantity_for_delivery` | Integer | 1 | Cantidad mínima de unidades para permitir envío a domicilio |

## Cómo Usar

### 1. Configurar manualmente en el panel administrativo Django

1. Ve a `http://localhost:8000/admin/`
2. Accede a **Configuración de Entregas por Producto**
3. Haz clic en **Agregar Configuración de Entregas**
4. Selecciona el producto
5. Marca o desmarca "Permitir domicilio"
6. Establece la cantidad mínima (si es necesario)
7. Guarda los cambios

### 2. Crear automáticamente (Recomendado)

Al crear un nuevo producto, **ProductDeliveryConfig se crea automáticamente** con valores por defecto:
- `allow_delivery = True`
- `min_quantity_for_delivery = 1`

### 3. Modificar desde código Django Shell

```python
from store.models import Product, ProductDeliveryConfig

# Obtener un producto
product = Product.objects.get(id=1)

# Acceder a su configuración de entrega
config = product.delivery_config

# Modificar
config.allow_delivery = False  # Deshabilitar domicilio
config.min_quantity_for_delivery = 5  # Mínimo 5 unidades
config.save()
```

## Casos de Uso Comunes

### Caso 1: Producto que NO puede enviarse a domicilio

```python
# Producto voluminoso o frágil
config = product.delivery_config
config.allow_delivery = False
config.save()

# Resultado: Los clientes pueden SOLO recoger en local
```

### Caso 2: Producto con cantidad mínima para envío

```python
# Producto al por menor que requiere cantidad mínima
config = product.delivery_config
config.allow_delivery = True
config.min_quantity_for_delivery = 10
config.save()

# Resultado: Los clientes DEBEN comprar mínimo 10 unidades si quieren envío
```

### Caso 3: Producto normal (Valores por defecto)

```python
# La mayoría de productos
config = product.delivery_config
# allow_delivery = True (por defecto)
# min_quantity_for_delivery = 1 (por defecto)

# Resultado: Se puede enviar a domicilio desde 1 unidad
```

## Validaciones en el Checkout

Durante el checkout, el sistema valida automáticamente:

1. **Si allow_delivery = False**: El usuario NO puede seleccionar "Envío a domicilio"
   - Mensaje de error: "El producto 'XXX' no permite envío a domicilio"

2. **Si cantidad < min_quantity_for_delivery**: El sistema rechaza el envío a domicilio
   - Mensaje de error: "Cantidad mínima para domicilio: X productos"

## Integración con Cálculo de Costos

```python
# Función _calculate_delivery_cost() en views.py

def _calculate_delivery_cost(request, delivery_option, delivery_zone=None):
    """
    Valida que todos los productos permitan domicilio antes de calcular costos
    """
    if delivery_option != "delivery":
        return Decimal("0.00"), None
    
    for item in items:
        product = item["product"]
        config = product.delivery_config
        
        # Verificar permisos
        if not config.allow_delivery:
            return None, f"El producto '{product.name}' no permite envío"
        
        # Verificar cantidad mínima
        if total_quantity < config.min_quantity_for_delivery:
            return None, f"Cantidad mínima: {config.min_quantity_for_delivery}"
    
    # Si pasa todas las validaciones, retornar costo
    return delivery_zone.cost, None
```

## Ejemplo de Carrito Rechazado

**Escenario**: Cliente intenta comprar 2 unidades de un producto que requiere mínimo 10 para envío

```
1. Cliente agrega 2 unidades al carrito
2. En checkout, selecciona "Envío a domicilio"
3. Sistema valida: 2 < 10 (mínimo requerido)
4. Resultado: ❌ Error - "Cantidad mínima para domicilio: 10 productos"
5. Cliente DEBE:
   - Aumentar a 10+ unidades, O
   - Cambiar a "Recoger en local"
```

## Testing

Tests unitarios para ProductDeliveryConfig en `store/tests.py`:

```python
# Ver: DeliveryAndCostCalculationTests

def test_delivery_cost_added_to_order_total(self):
    """Verifica que se calcula correctamente el costo de envío"""

def test_delivery_zone_saved_to_order(self):
    """Verifica que se guarda la zona de entrega en la orden"""

def test_pickup_has_zero_delivery_cost(self):
    """Verifica que recoger en local tiene costo 0"""
```

Ejecutar tests:
```bash
python manage.py test store.tests.DeliveryAndCostCalculationTests -v 2
```

## API Interna

### Atributos de Producto

```python
product = Product.objects.get(id=1)

# Acceso a la configuración
product.delivery_config.allow_delivery    # True/False
product.delivery_config.min_quantity_for_delivery  # Entero

# Verificar si puede entregarse
if product.delivery_config.allow_delivery:
    print("✅ Este producto SÍ se puede enviar")
else:
    print("❌ Este producto solo se puede recoger")
```

## FAQ

### P: ¿Qué pasa si elimino un producto?
**R**: La configuración de entrega se elimina automáticamente (CASCADE delete).

### P: ¿Puedo cambiar las restricciones de un producto activo?
**R**: Sí, puedes modificar en cualquier momento desde el Admin. Los cambios aplican a nuevas órdenes inmediatamente.

### P: ¿Qué pasa con órdenes antiguas si cambio la configuración?
**R**: Las órdenes ya creadas no se afectan. Solo impacta nuevas compras.

### P: ¿Puedo tener diferentes restricciones por zona de entrega?
**R**: No en la versión actual. ProductDeliveryConfig es global por producto. Considera crear variantes de producto si necesitas esto.

## Monitoreo

### Logs de auditoría

Los cambios en productos se registran automáticamente:

```
[INFO] Producto actualizado: Lámpara LED (ID=7), 
       Precio=$79.99, Stock=8, Activo=True, Destacado=True
```

Ver logs en: `logs/audit.log`

## Roadmap Futuro

- [ ] Restricciones por zona de entrega
- [ ] Restricciones por rango de fecha
- [ ] Configuración de horarios de entrega
- [ ] Integración con APIs de courier
