try:
    import framework32 as framework
except:
    import framework64 as framework

import math


# -------------------------------------------------------
#    Game parameters
# -------------------------------------------------------

class Params:
    EPSILON = 0.1
    DEGREES_EPS = 0.3
    WIN_WIDTH = 8.0
    WIN_HEIGHT = 6.0

    class Ship:
        LINEAR_SPEED = 0.5
        ANGULAR_SPEED = 0.5
        AIRCRAFT_COUNT = 5
        WIDTH = 0.6

    class Aircraft:
        ANGULAR_SPEED = 2.5
        CORRECT_ANGLE = 1.57
        FLIGHT_TIME = 45.0
        LINEAR_SPEED = 2.0
        LINEAR_SPEED_MIN = 0.1
        LINEAR_ACCELERATION = 1
        RELOAD_TIME = 3.0


# -------------------------------------------------------
#    Basic Vector2 class
# -------------------------------------------------------

class Vector2:

    def __init__(self, *args):
        if not args:
            self.x = self.y = 0.0
        elif len(args) == 1:
            self.x, self.y = args[0].x, args[0].y
        else:
            self.x, self.y = args

    def __abs__(self):
        return math.sqrt(self.x * self.x + self.y * self.y)

    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __mul__(self, coef):
        if isinstance(coef, Vector2):
            return self.x * coef.x + self.y * coef.y
        elif isinstance(coef, list):
            new_x = self.x * coef[0][0] - self.y * coef[0][1]
            new_y = self.x * coef[1][0] + self.y * coef[1][1]
            return Vector2(new_x, new_y)
        else:
            return Vector2(self.x * coef, self.y * coef)

    def is_null(self):
        return self.x < Params.EPSILON and \
               self.x > -Params.EPSILON and \
               self.y < Params.EPSILON and \
               self.y > -Params.EPSILON

    def angle_between(self, other):
        num = self * other
        denom = abs(self) * abs(other)
        value = num / denom
        return math.acos(1 if value > 1 else -1 if value < -1 else value)


# -------------------------------------------------------
#    Simple aircraft logic
# -------------------------------------------------------

class Aircraft:

    def __init__(self):
        # Acceleration vector
        self._a = None
        # Deflection angle
        self._angle = 0.0
        # Flight time
        self._flight_time = 0
        # Dict of the pressed keys
        self._input = None
        # Texture model
        self._model = None
        # The need to adjust the angle when circling around the target
        self._need_correct_angle = None
        # Current position
        self._position = None
        # Time for refueling
        self._reload_time = None
        # Aircraft rotation radius
        self._rotation_radius = None
        # Start position
        self._start_pos = None
        # Target for whirling in the air
        self._target = None
        # Velocity vector
        self._v = None
        # Velocity module
        self._v_abs = None

    def init(self, position, angle=None):
        assert not self._model
        self._a = Vector2(Params.Aircraft.LINEAR_ACCELERATION * math.cos(angle),
                          Params.Aircraft.LINEAR_ACCELERATION * math.sin(angle))
        self._angle = angle or 0.0
        self._flight_time = 0

        self._input = {
            framework.Keys.FORWARD: False,
            framework.Keys.BACKWARD: False,
            framework.Keys.LEFT: False,
            framework.Keys.RIGHT: False
        }

        self._model = framework.createAircraftModel()
        self._need_correct_angle = None
        self._position = Vector2(position)
        self._start_pos = Vector2(position)
        self._target = None
        self._reload_time = None
        self._v = Vector2(Params.Aircraft.LINEAR_SPEED_MIN * math.cos(angle),
                          Params.Aircraft.LINEAR_SPEED_MIN * math.sin(angle))
        self._v_abs = abs(self._v)
        self._rotation_radius = self._v_abs / Params.Aircraft.ANGULAR_SPEED

    def deinit(self, is_restart):
        if self._model is None:
            return

        self._reload_time = None if is_restart else 0
        framework.destroyModel(self._model)
        self._model = None

    def __flight_around(self, dt):
        """
        Aircraft spinning in a circle
        :param dt: quantum of the time
        :return:
        """
        self._angle += Params.Aircraft.ANGULAR_SPEED * dt
        rotate_vec = Vector2(math.cos(self._angle), math.sin(self._angle))
        self._v = rotate_vec * self._v_abs
        self._a = rotate_vec * abs(self._a)

    def __flight_to_target(self, target, dt, is_deinit=None):
        """
        Flight to the target
        :param target: target coordinates
        :param dt: quantum of the time
        :param is_deinit: hide the aircraft from the map
        :return:
        """
        target_vec = target - self._position
        if is_deinit and target_vec.is_null():
            self.deinit(False)
            return

        angle = target_vec.angle_between(self._v)
        if angle > Params.DEGREES_EPS:
            self.__flight_around(dt)

    def __flight_around_target(self, dt):
        """
        Flight around the target
        :param dt: quantum of the time
        :return:
        """
        target_vec = self._target - self._position
        # When the distance to the target becomes approximately equal to two radius of rotation,
        # it is necessary to adjust the course.
        # The correction vector is a vector perpendicular to the vector to the target
        # and equal in magnitude to the radius of rotation.
        # Vector A - vector perpendicular
        # Vector B - vector to the target
        # System:
        # Ax * Bx + Ay * By = 0
        # Ax * Ax + Ay * Ay = R
        # Decision:
        # Ay = R / sqrt(1 + (By / Bx)^2)
        # Ax = - Ay * (By / Bx)
        if abs(target_vec) <= self._rotation_radius:
            if self._need_correct_angle and target_vec.x != 0:
                koef = target_vec.y / target_vec.x
                ay = self._rotation_radius / math.sqrt(1 + koef ** 2)
                ax = ay * koef
                if target_vec.x > 0:
                    self._target.x += ax
                    self._target.y -= ay
                elif target_vec.x < 0:
                    self._target.x -= ax
                    self._target.y += ay
                self._need_correct_angle = False
        if target_vec.is_null():
            self.__flight_around(dt)
        else:
            self.__flight_to_target(self._target, dt)

    def update(self, dt, ship_pos, ship_angle):
        if self._model is None:
            # Wait some time for reloaded aircraft
            if self._reload_time is not None:
                self._reload_time += dt
            return

        # If the aircraft flew over the edges of the screen,
        # then we direct it in the opposite direction
        if self._position.y > Params.WIN_HEIGHT or \
                self._position.y < -Params.WIN_HEIGHT or \
                self._position.x > Params.WIN_WIDTH or \
                self._position.x < -Params.WIN_WIDTH:
            self.__flight_to_target(self._position * (-1), dt)

        # Increase the velocity to the maximum value
        if self._v_abs < Params.Aircraft.LINEAR_SPEED:
            # When the aircraft accelerates through the ship
            if abs(self._position - self._start_pos) < Params.Ship.WIDTH:
                self._a = Vector2(math.cos(ship_angle), math.sin(ship_angle)) * abs(self._a)
                self._v = Vector2(math.cos(ship_angle), math.sin(ship_angle)) * self._v_abs
                self._angle = ship_angle
            # When the aircraft accelerates and flight to target
            elif self._target is not None:
                self.__flight_around_target(dt)
            self._v += self._a * dt
            self._v_abs = abs(self._v)
            self._rotation_radius = self._v_abs / Params.Aircraft.ANGULAR_SPEED
        # Increase the flight time to the maximum value
        elif self._flight_time < Params.Aircraft.FLIGHT_TIME:
            self._flight_time += dt
            # If target init - the aircraft circles around the target
            if self._target is not None:
                self.__flight_around_target(dt)
        else:
            # Return to the ship
            self.__flight_to_target(ship_pos, dt, True)

        # Aircraft return to the ship
        if self._model is None:
            return

        self._position += self._v * dt
        framework.placeModel(self._model, self._position.x, self._position.y, self._angle)

    def keyPressed(self, key):
        self._input[key] = True

    def keyReleased(self, key):
        self._input[key] = False

    def mouseClicked(self, x, y, isLeftButton):
        pass

    def is_hidden(self):
        return self._model is None

    def set_target(self, x, y):
        if self.is_hidden():
            return

        self._target = Vector2(x, y)
        self._need_correct_angle = True

    def is_reloaded(self):
        return self._reload_time is not None and self._reload_time < Params.Aircraft.RELOAD_TIME


# -------------------------------------------------------
#    Simple ship logic
# -------------------------------------------------------

class Ship:

    def __init__(self):
        self._model = None
        self._position = None
        self._angle = 0.0
        self._input = None
        self._aircrafts = [Aircraft() for i in range(Params.Ship.AIRCRAFT_COUNT)]

    def init(self):
        assert not self._model
        self._model = framework.createShipModel()
        self._position = Vector2()
        self._angle = 0.0
        self._input = {
            framework.Keys.FORWARD: False,
            framework.Keys.BACKWARD: False,
            framework.Keys.LEFT: False,
            framework.Keys.RIGHT: False
        }

    def deinit(self):
        assert self._model
        framework.destroyModel(self._model)
        self._model = None
        for aircraft in self._aircrafts:
            aircraft.deinit(True)

    def update(self, dt):
        linearSpeed = 0.0
        angularSpeed = 0.0

        if self._input[framework.Keys.FORWARD]:
            linearSpeed = Params.Ship.LINEAR_SPEED
        elif self._input[framework.Keys.BACKWARD]:
            linearSpeed = -Params.Ship.LINEAR_SPEED

        if self._input[framework.Keys.LEFT] and linearSpeed != 0.0:
            angularSpeed = Params.Ship.ANGULAR_SPEED
        elif self._input[framework.Keys.RIGHT] and linearSpeed != 0.0:
            angularSpeed = -Params.Ship.ANGULAR_SPEED

        self._angle = self._angle + angularSpeed * dt
        self._position = self._position + Vector2(math.cos(self._angle), math.sin(self._angle)) * linearSpeed * dt
        framework.placeModel(self._model, self._position.x, self._position.y, self._angle)

        for aircraft in self._aircrafts:
            aircraft.update(dt, self._position, self._angle)

    def keyPressed(self, key):
        self._input[key] = True

    def keyReleased(self, key):
        self._input[key] = False

    def mouseClicked(self, x, y, isLeftButton):
        if isLeftButton:
            framework.placeGoalModel(x, y)
            for aircraft in self._aircrafts:
                aircraft.set_target(x, y)
        else:
            for aircraft in self._aircrafts:
                if aircraft.is_hidden() and not aircraft.is_reloaded():
                    aircraft.init(self._position, self._angle)
                    break


# -------------------------------------------------------
#    Game public interface
# -------------------------------------------------------

class Game:

    def __init__(self):
        self._ship = Ship()

    def init(self):
        self._ship.init()

    def deinit(self):
        self._ship.deinit()

    def update(self, dt):
        self._ship.update(dt)

    def keyPressed(self, key):
        self._ship.keyPressed(key)

    def keyReleased(self, key):
        self._ship.keyReleased(key)

    def mouseClicked(self, x, y, isLeftButton):
        self._ship.mouseClicked(x, y, isLeftButton)


# -------------------------------------------------------
#    Finally we can run our game!
# -------------------------------------------------------

framework.runGame(Game())
