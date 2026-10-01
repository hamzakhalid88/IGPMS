-- 1. Naya SQL Login (Complex Password - Policy ko satisfy karega)
CREATE LOGIN python_app WITH PASSWORD = 'Python@2024#';
GO

-- 2. 'cpms' database mein user banayein
USE cpms;
CREATE USER python_app FOR LOGIN python_app;
GO

-- 3. Data Padhne (SELECT) ki permission
ALTER ROLE db_datareader ADD MEMBER python_app;
GO

-- 4. Agar Insert/Update bhi karna hai toh yeh bhi chala dein
ALTER ROLE db_datawriter ADD MEMBER python_app;
GO