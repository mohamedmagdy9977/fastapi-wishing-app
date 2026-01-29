import qrcode
data = 'https://229c0bad07c8.ngrok-free.app/'

img = qrcode.make(data)
img.save('MyQRCode1.png')