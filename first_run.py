"""First-run administrator password setup."""

def request_admin_password():
    import customtkinter as ctk
    from auth import is_strong_password

    result = {"password": None}

    root = ctk.CTk()
    root.title("AOMS - First Run Setup")
    root.geometry("480x430")
    root.resizable(False, False)

    ctk.CTkLabel(
        root, text="AOMS", font=ctk.CTkFont(size=30, weight="bold")
    ).pack(pady=(30, 5))

    ctk.CTkLabel(
        root, text="Create your administrator password"
    ).pack(pady=5)

    password = ctk.CTkEntry(
        root, width=340, height=42,
        placeholder_text="New password", show="*"
    )
    password.pack(pady=12)

    confirm = ctk.CTkEntry(
        root, width=340, height=42,
        placeholder_text="Confirm password", show="*"
    )
    confirm.pack(pady=8)

    message = ctk.CTkLabel(
        root, text="", text_color="#ef4444",
        wraplength=380
    )
    message.pack(pady=8)

    ctk.CTkLabel(
        root,
        text="Minimum 8 characters: uppercase, lowercase, digit and symbol.",
        wraplength=380
    ).pack(pady=5)

    def submit():
        first = password.get()
        second = confirm.get()

        valid, reason = is_strong_password(first)

        if not valid:
            message.configure(text=reason)
            return

        if first != second:
            message.configure(text="Passwords do not match.")
            return

        result["password"] = first
        root.destroy()

    ctk.CTkButton(
        root, text="Create Administrator Account",
        width=340, height=44, command=submit
    ).pack(pady=15)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    password.focus()
    root.mainloop()

    return result["password"]
