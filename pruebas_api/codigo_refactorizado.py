def cobrar_tarjeta(monto: float) -> bool:
    if monto <= 0:
        print("Error: Monto invalido")
        return False
    print(f"Cobrando ${monto} de la tarjeta...")
    return True


def enviar_recibo(correo: str, monto: float) -> None:
    print("Conectando al servidor de correos...")
    print(f"Enviando recibo a {correo}")
    print(f"Mensaje: Su pago de ${monto} fue exitoso.")


def procesar_pago(monto: float, correo: str) -> bool:
    if not cobrar_tarjeta(monto):
        return False
    
    enviar_recibo(correo, monto)
    return True