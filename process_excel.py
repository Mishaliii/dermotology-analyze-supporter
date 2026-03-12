import pandas as pd

# Load WHO Excel
df = pd.read_excel("EML export (1).xlsx")

# Convert everything to lowercase for filtering
df["lower_name"] = df.astype(str).apply(lambda x: x.str.lower())

# Dermatology keyword filter
keywords = [
    "hydrocortisone",
    "clobetasol",
    "betamethasone",
    "adapalene",
    "tretinoin",
    "benzoyl",
    "doxycycline",
    "clindamycin",
    "ketoconazole",
    "fluconazole",
    "itraconazole",
    "tacrolimus",
    "pimecrolimus",
    "methotrexate",
    "cyclosporine",
    "minoxidil",
    "finasteride"
]

filtered = df[df["lower_name"].apply(
    lambda row: any(k in row for k in keywords)
)]

filtered.to_csv("dermatology_medicines_filtered.csv", index=False)