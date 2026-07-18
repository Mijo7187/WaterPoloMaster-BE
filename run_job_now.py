import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Import all models so SQLAlchemy mapper resolves every relationship
import app.features.users.users_models
import app.features.company.company_model
import app.features.sifarnici.country.country_model
import app.features.sifarnici.city.city_model
import app.features.training.training_model
import app.features.wallet.wallet_model
import app.features.payment.payment_model
import app.features.sifarnici.payment_type.payment_type_model
import app.features.training_users_list.training_users_list_model

from app.scheduler.training_jobs import run_nightly_training_job

print("Running nightly training job now...")
run_nightly_training_job()
print("Done.")
