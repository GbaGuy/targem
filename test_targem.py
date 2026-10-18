from targem import clean_ocr, parse_google, split_sentences

assert clean_ocr("Hello there,\n  traveler!\n|\n\n~ .\nWelcome.") == "Hello there, traveler! Welcome."
assert clean_ocr("") == ""
assert parse_google([[["שלום ", "Hello ", None], ["עולם", "world", None]], None, "en"]) == "שלום עולם"
assert split_sentences("Quest complete! You got 5 XP. Wait... what?") == ["Quest complete!", "You got 5 XP.", "Wait...", "what?"]
assert split_sentences("v1.5 is out") == ["v1.5 is out"]
print("ok")
