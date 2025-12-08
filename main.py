import os
import google.generativeai as genai

def main():
    print("Hello from macro!")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    genai.configure(api_key=api_key)
    #model = genai.GenerativeModel('gemini-flash-lite-latest')
    model = genai.GenerativeModel('gemini-pro-latest')
    #gemini-pro-latest
    
    try:
        response = model.generate_content("Explain how AI works in five sentence.")
        print("\nGemini says:")
        print(response.text)
    except Exception as e:
        print(f"\nError querying Gemini: {e}")

if __name__ == "__main__":
    main()
