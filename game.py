try:
    import framework32 as framework
except:
    import framework64 as framework

import math

# -------------------------------------------------------
#	game parameters
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

    class Aircraft:
        LINEAR_SPEED = 2.0
        LINEAR_SPEED_MIN = 0.5
        LINEAR_ACCELERATION = 1
        ANGULAR_SPEED = 2.5
        FLIGHT_TIME = 15.0
        RELOAD_TIME = 3.0


# -------------------------------------------------------
#	Basic Vector2 class
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
#	Simple aircraft logic
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
        # Current position
        self._position = None
        # Time for refueling
        self._reload_time = None
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
        self._position = Vector2(position)
        self._target = None
        self._reload_time = None
        self._v = Vector2(Params.Aircraft.LINEAR_SPEED_MIN * math.cos(angle),
                          Params.Aircraft.LINEAR_SPEED_MIN * math.sin(angle))
        self._v_abs = abs(self._v)

    def deinit(self):
        if self._model is None:
            return

        self._reload_time = 0
        framework.destroyModel(self._model)
        self._model = None

    def __flight_around(self, dt):
        """
        Aircraft spinning in a circle
        :param dt: quantum of the time
        :return:
        """
        self._angle += Params.Aircraft.ANGULAR_SPEED * dt
        self._v = Vector2(math.cos(self._angle), math.sin(self._angle)) * self._v_abs

    def __flight_to_target(self, target, dt, is_deinit=None):
        """
        Flight to the target
        :param target: target coordinates
        :param dt: quantum of the time
        :param is_deinit: hide the aircraft from the map
        :return:
        """
        target_vec = Vector2(target.x - self._position.x,
                             target.y - self._position.y)
        if is_deinit and target_vec.is_null():
            self.deinit()
            return

        angle = target_vec.angle_between(self._v)
        if angle > Params.DEGREES_EPS:
            self.__flight_around(dt)
        else:
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            # Multiplication of a vector by a rotation matrix
            self._v = self._v * [[cos_angle, sin_angle], [sin_angle, cos_angle]]

    def __flight_around_the_target(self, dt):
        """
        Flight around the target
        :param dt: quantum of the time
        :return:
        """
        target_vec = Vector2(self._target.x - self._position.x,
                             self._target.y - self._position.y)
        if abs(target_vec) <= self._v_abs / Params.Aircraft.ANGULAR_SPEED:
            self.__flight_around(dt)
        else:
            self.__flight_to_target(self._target, dt)

    def update(self, dt, ship_pos):
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
            self._v += self._a * dt
            self._v_abs = abs(self._v)
        # Increase the flight time to the maximum value
        elif self._flight_time < Params.Aircraft.FLIGHT_TIME:
            self._flight_time += dt
            # If target init - the aircraft circles around the target
            if self._target is not None:
                self.__flight_around_the_target(dt)
        else:
            # Return to the ship
            self.__flight_to_target(ship_pos, dt, True)

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

    def is_reloaded(self):
        return self._reload_time is not None and self._reload_time < Params.Aircraft.RELOAD_TIME

# -------------------------------------------------------
#	Simple ship logic
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
            aircraft.deinit()

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
            aircraft.update(dt, self._position)

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
#	game public interface
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
#	finally we can run our game!
# -------------------------------------------------------

framework.runGame(Game())