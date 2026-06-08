import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Client, Company, Project, Role, User, UserClientAccess, UserRole
from app.services.permissions import ensure_default_permissions, permission_code, set_role_permissions


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requiere RUN_DB_TESTS=1")
class TenancyPermissionsDBTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        self.suffix = uuid4().hex[:10]
        self.permissions = {
            permission_code(permission.module, permission.action): permission
            for permission in ensure_default_permissions(self.db)
        }

        self.company_a = self._create_company("A")
        self.company_b = self._create_company("B")
        self.user_a = self._create_user(
            self.company_a,
            "Usuario A",
            permissions=["clients:view", "clients:create"],
        )
        self.user_without_permissions = self._create_user(
            self.company_a,
            "Usuario sin permisos",
            permissions=[],
        )
        self.master_user = self._create_user(
            None,
            "Administrador maestro",
            permissions=[],
            is_master_admin=True,
        )

        self.client_a = self._create_client(self.company_a, "Desarrolladora A")
        self.client_a_restricted_hidden = self._create_client(
            self.company_a,
            "Desarrolladora A oculta",
        )
        self.client_b = self._create_client(self.company_b, "Desarrolladora B")
        self.project_a = self._create_project(self.company_a, self.client_a, "Proyecto A")
        self.project_a_hidden = self._create_project(
            self.company_a,
            self.client_a_restricted_hidden,
            "Proyecto A oculto",
        )
        self.restricted_user = self._create_user(
            self.company_a,
            "Usuario restringido",
            permissions=["clients:view", "projects:view"],
        )
        self.restricted_user.client_access_mode = "restricted"
        self.db.add(
            UserClientAccess(
                company_id=self.company_a.id,
                user_id=self.restricted_user.id,
                client_id=self.client_a.id,
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self.db.close()

    def _create_company(self, label: str) -> Company:
        company = Company(
            name=f"Constructora {label} {self.suffix}",
            legal_name=f"Constructora {label} {self.suffix} SA de CV",
            contact_email=f"empresa-{label.lower()}-{self.suffix}@example.com",
            license_status="active",
        )
        self.db.add(company)
        self.db.flush()
        return company

    def _create_user(
        self,
        company: Company | None,
        full_name: str,
        permissions: list[str],
        is_master_admin: bool = False,
    ) -> User:
        user = User(
            company_id=company.id if company else None,
            full_name=f"{full_name} {self.suffix}",
            email=f"{full_name.lower().replace(' ', '-')}-{self.suffix}@example.com",
            password_hash=get_password_hash("Admin12345!"),
            is_active=True,
            is_master_admin=is_master_admin,
        )
        self.db.add(user)
        self.db.flush()

        if permissions:
            role = Role(
                company_id=company.id if company else None,
                name=f"Rol {full_name} {self.suffix}",
                description="Rol de prueba de permisos y aislamiento",
                is_system_role=False,
            )
            self.db.add(role)
            self.db.flush()
            set_role_permissions(
                self.db,
                role.id,
                [self.permissions[code].id for code in permissions],
            )
            self.db.add(UserRole(user_id=user.id, role_id=role.id))
            self.db.flush()

        return user

    def _create_client(self, company: Company, name: str) -> Client:
        client = Client(
            company_id=company.id,
            name=f"{name} {self.suffix}",
            contact_email=f"{name.lower().replace(' ', '-')}-{self.suffix}@example.com",
        )
        self.db.add(client)
        self.db.flush()
        return client

    def _create_project(self, company: Company, client: Client, name: str) -> Project:
        project = Project(
            company_id=company.id,
            client_id=client.id,
            name=f"{name} {self.suffix}",
            status="draft",
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _headers_for(self, user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    def test_tenant_user_only_sees_own_clients(self) -> None:
        response = self.client.get("/api/v1/clients", headers=self._headers_for(self.user_a))

        self.assertEqual(response.status_code, 200)
        client_names = {item["name"] for item in response.json()}
        self.assertIn(self.client_a.name, client_names)
        self.assertIn(self.client_a_restricted_hidden.name, client_names)
        self.assertNotIn(self.client_b.name, client_names)

    def test_restricted_user_only_sees_assigned_clients(self) -> None:
        response = self.client.get("/api/v1/clients", headers=self._headers_for(self.restricted_user))

        self.assertEqual(response.status_code, 200)
        client_names = {item["name"] for item in response.json()}
        self.assertIn(self.client_a.name, client_names)
        self.assertNotIn(self.client_a_restricted_hidden.name, client_names)
        self.assertNotIn(self.client_b.name, client_names)

    def test_restricted_user_only_sees_projects_for_assigned_clients(self) -> None:
        response = self.client.get("/api/v1/projects", headers=self._headers_for(self.restricted_user))

        self.assertEqual(response.status_code, 200)
        project_names = {item["name"] for item in response.json()}
        self.assertIn(self.project_a.name, project_names)
        self.assertNotIn(self.project_a_hidden.name, project_names)

    def test_restricted_user_gets_not_found_for_unassigned_client(self) -> None:
        response = self.client.get(
            f"/api/v1/clients/{self.client_a_restricted_hidden.id}",
            headers=self._headers_for(self.restricted_user),
        )

        self.assertEqual(response.status_code, 404)

    def test_foreign_client_is_hidden_as_not_found_for_tenant_user(self) -> None:
        response = self.client.get(
            f"/api/v1/clients/{self.client_b.id}",
            headers=self._headers_for(self.user_a),
        )

        self.assertEqual(response.status_code, 404)

    def test_master_user_can_see_all_clients(self) -> None:
        response = self.client.get("/api/v1/clients", headers=self._headers_for(self.master_user))

        self.assertEqual(response.status_code, 200)
        client_names = {item["name"] for item in response.json()}
        self.assertIn(self.client_a.name, client_names)
        self.assertIn(self.client_b.name, client_names)

    def test_tenant_create_ignores_foreign_company_id_in_payload(self) -> None:
        response = self.client.post(
            "/api/v1/clients",
            headers=self._headers_for(self.user_a),
            json={
                "company_id": self.company_b.id,
                "name": f"Desarrolladora inyectada {self.suffix}",
                "contact_email": f"inyectada-{self.suffix}@example.com",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company_id"], self.company_a.id)

    def test_missing_permission_returns_forbidden(self) -> None:
        response = self.client.get(
            "/api/v1/clients",
            headers=self._headers_for(self.user_without_permissions),
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
