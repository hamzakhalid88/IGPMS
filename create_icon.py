from PIL import Image, ImageDraw, ImageFont

def create_imei_icon():
    # Create a 64x64 icon with blue background
    img = Image.new('RGB', (64, 64), color='#0078D7')
    d = ImageDraw.Draw(img)
    
    # Draw border
    d.rectangle([(0,0), (63,63)], outline='white', width=2)
    
    # Draw "IMEI" text
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    d.text((8, 20), "IMEI", fill='white', font=font)
    
    # Save as .ico
    img.save('icon.ico', format='ICO')
    print("Icon created: icon.ico")
    
    # Also save as PNG for cross-platform
    img.save('icon.png')
    print("Icon created: icon.png")

if __name__ == "__main__":
    create_imei_icon()