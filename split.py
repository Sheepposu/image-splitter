import math
from PIL import Image
import pygame
import tkinter
import tkinter.filedialog
import traceback
from typing import List, Tuple, Optional, Sequence


class SplitPoint:
    def __init__(self, point: Tuple[int, int]):
        self.pos: pygame.Rect = pygame.Rect(point[0], point[1], 0, 0)
        self.horizontal: Optional[Tuple[int, int]] = None
        self.vertical: Optional[Tuple[int, int]] = None
        self.index = 0

    def toggle_horizontal(self, width):
        if self.horizontal is None:
            self.horizontal = (0, width)
        else:
            self.horizontal = None

    def toggle_vertical(self, height):
        if self.vertical is None:
            self.vertical = (0, height)
        else:
            self.vertical = None

    def reset_bounds(self, screen_size):
        if self.horizontal is not None:
            self.horizontal = (0, screen_size[0])
        if self.vertical is not None:
            self.vertical = (0, screen_size[1])

    def distance_to(self, point):
        return math.sqrt(math.pow(point[0]-self.pos[0], 2)+math.pow(point[1]-self.pos[1], 2))


class SplitStateManager:
    def __init__(self, screen_size, dot_radius):
        self.screen_size: Tuple[int, int] = screen_size
        self.dot_radius: int = dot_radius

        self.placing = False
        self.deleting = False
        self.split_points: List[SplitPoint] = []
        self.selected_point: Optional[SplitPoint] = None

    def on_mouse_down(self):
        if (press := pygame.mouse.get_pressed())[0]:
            self.placing = True
        elif press[2]:
            self.deleting = True

    def on_mouse_up(self):
        if self.placing:
            self.add_point()
        elif self.deleting:
            self.delete_point()

    def add_point(self):
        current_point = pygame.mouse.get_pos()
        for p in self.split_points:
            if p.distance_to(current_point) <= self.dot_radius:
                self.selected_point = p
                print(f"Current index: {self.selected_point.index}")
                return
        self.split_points.append(SplitPoint(current_point))
        self.placing = False
        self.selected_point = self.split_points[-1]

    def delete_point(self):
        point = pygame.mouse.get_pos()
        for p in self.split_points:
            if p.distance_to(point) <= self.dot_radius:
                self.split_points.remove(p)
                if p == self.selected_point:
                    self.selected_point = None
                break
        self.deleting = False
        self.calculate_line_rects()

    def horizontal_split(self):
        if self.selected_point is None: return
        self.selected_point.toggle_horizontal(self.screen_size[0])
        self.calculate_line_rects()

    def vertical_split(self):
        if self.selected_point is None: return
        self.selected_point.toggle_vertical(self.screen_size[1])
        self.calculate_line_rects()

    def increment_index(self):
        if self.selected_point is None: return
        self.selected_point.index += 1
        print(f"New index: {self.selected_point.index}")
        self.calculate_line_rects()

    def decrement_index(self):
        if self.selected_point is None: return
        self.selected_point.index -= 1
        print(f"New index: {self.selected_point.index}")
        self.calculate_line_rects()

    def _calculate_bounds(self, bound, lower_bound, upper_bound, bounds):
        for other_bound in bounds:
            if bound > other_bound > lower_bound:
                lower_bound = other_bound
            elif upper_bound > other_bound > bound:
                upper_bound = other_bound
        return lower_bound, upper_bound

    def calculate_line_rects(self):
        points = sorted(self.split_points, key=lambda p: p.index)
        for i in range(len(points)):
            point = points[i]
            point.reset_bounds(self.screen_size)
            prior_points = tuple(filter(lambda p: p.index != point.index, points[:i]))
            if len(prior_points) == 0:
                continue
            if point.horizontal is not None:
                point.horizontal = self._calculate_bounds(point.pos[0], *point.horizontal, map(
                    lambda p: p.pos[0], filter(
                        lambda p: p.vertical is not None, prior_points
                    )
                ))
            if point.vertical is not None:
                point.vertical = self._calculate_bounds(point.pos[1], *point.vertical, map(
                    lambda p: p.pos[1], filter(
                        lambda p: p.horizontal is not None, prior_points
                    )
                ))

    def group_points(self) -> List[List[SplitPoint]]:
        groups: List[List[SplitPoint]] = [[]]
        for point in sorted(filter(lambda p: p.horizontal is not None or p.vertical is not None,
                                   self.split_points),
                            key=lambda p: p.index):
            if len(groups[-1]) == 0:
                groups[-1].append(point)
                continue
            if groups[-1][0].index == point.index:
                groups[-1].append(point)
            else:
                groups.append([point])
        return groups

    def subdivide_box(self, box: pygame.Rect, points: Sequence[SplitPoint]):
        boxes = []
        vertical_cuts = list(map(lambda p: p.pos[0], filter(lambda p: p.vertical is not None, points)))
        vertical_cuts.append(box.right)
        horizontal_cuts = list(map(lambda p: p.pos[1], filter(lambda p: p.horizontal is not None, points)))
        horizontal_cuts.append(box.bottom)
        for ix in range(len(vertical_cuts)):
            x1 = box[0] if ix == 0 else vertical_cuts[ix - 1]
            x2 = vertical_cuts[ix]
            for iy in range(len(horizontal_cuts)):
                y1 = box[1] if iy == 0 else horizontal_cuts[iy-1]
                y2 = horizontal_cuts[iy]
                boxes.append(pygame.Rect(x1, y1, x2-x1, y2-y1))
        return boxes

    def calculate_boxes(self) -> List[pygame.Rect]:
        groups = self.group_points()
        boxes = [pygame.Rect(0, 0, self.screen_size[0], self.screen_size[1])]
        i = 0
        while i < len(groups):
            for box in tuple(boxes):
                new_boxes = self.subdivide_box(box, tuple(filter(lambda p: box.contains(p.pos), groups[i])))
                boxes.remove(box)
                boxes += new_boxes
            i += 1
        return boxes


class ImageSplitter:
    FPS = 30
    DOT_RADIUS = 5
    DOT_COLOR = (0, 0, 0)
    SELECT_COLOR = (0, 255, 0)

    def __init__(self):
        pygame.init()
        self.image_path = self.get_file()
        self.image = pygame.image.load(self.image_path)
        self.screen = pygame.display.set_mode(self.image.get_size())
        self.clock = pygame.time.Clock()
        self.running = False

        self.splitter = SplitStateManager(self.screen.get_size(), self.DOT_RADIUS)

    def get_file(self):
        top = tkinter.Tk()
        top.withdraw()
        path = tkinter.filedialog.askopenfilename(parent=top)
        top.destroy()
        return path

    def export_image(self):
        try:
            image = Image.open(self.image_path)
            extension = self.image_path.split(".")[-1]
            for i, box in enumerate(self.splitter.calculate_boxes()):
                cropped_image = image.crop((box.left, box.top, box.right, box.bottom))
                cropped_image.save(f"output/im{i}.{extension}")
            print("Exported!")
        except FileNotFoundError:
            print("A file error occurred... make sure the image was not moved or deleted "
                  "and a directory named 'output' exists in the running directory")
        except:
            traceback.print_exc()

    def handle_keys(self, event):
        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.splitter.horizontal_split()
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            self.splitter.vertical_split()
        elif event.key == pygame.K_l:
            self.splitter.decrement_index()
        elif event.key == pygame.K_SEMICOLON:
            self.splitter.increment_index()
        elif event.key == pygame.K_e:
            self.export_image()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            elif event.type == pygame.MOUSEBUTTONUP:
                self.splitter.on_mouse_up()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.splitter.on_mouse_down()
            elif event.type == pygame.KEYUP:
                self.handle_keys(event)
        return True

    def draw_split_point(self, point: SplitPoint, *, selector=False):
        pygame.draw.circle(self.screen, self.SELECT_COLOR if selector else self.DOT_COLOR, point.pos.center,
                           self.DOT_RADIUS + (2 if selector else 0))
        if not selector:
            if point.horizontal is not None:
                pygame.draw.line(self.screen, self.DOT_COLOR, (point.horizontal[0], point.pos[1]),
                                 (point.horizontal[1], point.pos[1]))
            if point.vertical is not None:
                pygame.draw.line(self.screen, self.DOT_COLOR, (point.pos[0], point.vertical[0]),
                                 (point.pos[0], point.vertical[1]))

    def draw(self):
        self.screen.blit(self.image, (0, 0))
        if self.splitter.selected_point is not None:
            self.draw_split_point(self.splitter.selected_point, selector=True)
        for point in self.splitter.split_points:
            self.draw_split_point(point)

    def run(self):
        self.running = True
        while self.running:
            if not self.handle_events():
                break
            self.draw()
            pygame.display.update()
            self.clock.tick(self.FPS)


if __name__ == "__main__":
    print("HOW TO USE:\n"
          "Place/select point: left click\n"
          "Delete point: right click\n"
          "Create horizontal line on current point: left/right arrow\n"
          "Create vertical line on current point: up/down arrow\n"
          "Increment point index: ;\n"
          "Decrement point index: L\n"
          "Export (to ./output): E\n"
          "Index meaning: lower index lines block higher index lines\n"
          "See point index: select a point to see its index\n"
          "NOTE: MUST CREATE A DIRECTORY NAMED 'output' IN THE RUNNING DIRECTORY TO EXPORT.\n"
          "To start, pick an image file.\n")
    app = ImageSplitter()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
