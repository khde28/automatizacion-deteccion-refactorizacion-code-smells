class Pago:
    def __init__(self, monto, correo):
        self.monto = monto
        self.correo = correo

    def procesar_pago(self):
        if self._validar_monto():
            print(f"Cobrando ${self.monto} de la tarjeta...")
            return self._enviar_recibo()
        else:
            print("Error: Monto invalido")
            return False

    @staticmethod
    def _validar_monto(monto):
        if monto <= 0:
            raise ValueError("Monto invalido")

    @staticmethod
    def _enviar_recibo(correo, mensaje):
        print(f"Conectando al servidor de correos...")
        print(f"Enviando recibo a {correo}")
        print(f"Mensaje: {mensaje}")


def main():
    pago = Pago(100, "ejemplo@example.com")
    if pago.procesar_pago():
        print("Pago exitoso")


if __name__ == "__main__":
    main()