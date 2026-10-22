# Helios

Helios is a Python web framework designed for supporting personal-scale web
applications. It prioritizes *clarity*, *expressiveness*, and *composability*.
It aims to be small enough to read & understand in a few days of concentrated
study. It is thematically inspired by [Laravel](https://laravel.com) and
[Hono](https://hono.dev).

Helios is made up of a core and a series of optional components. An application
can use as many or as few of the components as it needs.

The core consists of:
- [Application lifetime management and dependency containers for both
  application- and request- scoped objects](packages/framework/src/helios/app/)
- [HTTP request and response handling](packages/framework/src/helios/http/)
- [Routing with typed route parameters](packages/framework/src/helios/routing/)
- [Nested configuration and environment
  loading](packages/framework/src/helios/config.py)

The available components are:
- [Database modeling backed by SQLite](packages/framework/src/helios/database/)
- [View rendering](packages/view/src/helios/view/)
- [Form validation](packages/framework/src/helios/form/)
- [File-backed sessions](packages/framework/src/helios/session/)
- [Authentication](packages/framework/src/helios/auth/)
- [Rate limiting](packages/framework/src/helios/limit/)
