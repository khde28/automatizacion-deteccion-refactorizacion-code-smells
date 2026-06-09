def procesar_pago(monto, correo):
    # Parte 1: Lógica de cobro
    if monto <= 0:
        print("Error: Monto invalido")
        return False
    print(f"Cobrando ${monto} de la tarjeta...")
    
    # Parte 2: Envío de recibo
    print(f"Conectando al servidor de correos...")
    print(f"Enviando recibo a {correo}")
    print(f"Mensaje: Su pago de ${monto} fue exitoso.")
    
    return True
