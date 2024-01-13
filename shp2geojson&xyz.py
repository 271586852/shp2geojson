from flask import Flask, request, jsonify
import geopandas as gpd
import os
import json


from osgeo import gdal, ogr,osr

def shp2xyz(shpin, txt_path):
    '''
    collector of functions that reformats shapefiles (.shp) to .xyz files
    :param shpin: shapefile (point, line, or polygon)
    :param xyz: filename to store output
    :return: MIKE compatible .xyz formated shapefile
    '''
    xyz = txt_path
    shp_ds = ogr.Open(shpin)
    shp_lyr = shp_ds.GetLayer()

    # gets the shapefile type and applies the necessary function
    if shp_lyr.GetGeomType() == 1:
        print("Type: point")
        point2xyz(shpin, xyz)
    elif shp_lyr.GetGeomType() == 2:
        print("Type: polyline")
        line2xyz(shpin, xyz)
    elif shp_lyr.GetGeomType() == 3:
        print("Type: polygon")
        poly2xyz(shpin, xyz)


def point2xyz(shpin, xyz):
    '''
    reformat point-type .shp to .xyz
    :param shpin:
    :param xyz:
    :return:
    '''
    shp_ds = ogr.Open(shpin)
    shp_lyr = shp_ds.GetLayer()

    print ('found %d number of features!' % len(shp_lyr))

    fopen = open(xyz, 'a')

    for feat in shp_lyr:
        geom = feat.GetGeometryRef()
        print (geom.GetGeometryType())

        connectivity = feat.GetFieldAsInteger('CON')
        print (connectivity)
        line = ''.join([str(geom.GetX()), ' ', str(geom.GetY()), ' ', str(connectivity), '\n'])
        fopen.write(line)

    fopen.close()

def line2xyz(shpin, txt_path):
    '''
    reformat line-type .shp to .xyz
    :param shpin:
    :param xyz:
    :return:
    '''
    first_line = True

    # txt_out = xyz
    shp_ds = ogr.Open(shpin)
    if shp_ds is None:
        raise ValueError(f"Could not open shapefile: {shpin}")

    shp_lyr = shp_ds.GetLayer()
    print('found %d number of features!' % len(shp_lyr))

    # 获取地理参考
    shp_srs = shp_lyr.GetSpatialRef()
    print('Shapefile Coordinate System:', shp_srs)

    # 创建转换对象 CGCS2000
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(4490)  # CGCS2000 EPSG code
    transform = osr.CoordinateTransformation(shp_srs, target_srs)

    line_count = 0
    interp_line_count = 0

    with open(txt_path, 'w') as fopen:

        for feat in shp_lyr:
            geom = feat.GetGeometryRef()
            # geom.Transform(transform)  # 转换到CGCS2000
            print(geom.GetGeometryName())
            print(geom.GetPointCount())
            for i in range(0, geom.GetPointCount()):
                if first_line:
                    line = ''.join([str(geom.GetPoint(i)[0]), ' ', str(geom.GetPoint(i)[1]), ' ', '1\n'])
                    first_line = False
                else:
                    line = ''.join([str(geom.GetPoint(i)[0]), ' ', str(geom.GetPoint(i)[1]), ' ', '0\n'])
                print('line', line)
                fopen.write(line)
                line_count += 1
                # 添加中点值
                if i < geom.GetPointCount() - 1:
                    # 线性插值
                    num_points = 5  # 设置插值点的数量
                    for j in range(1, num_points):
                        interp_x = geom.GetPoint(i)[0] + (geom.GetPoint(i+1)[0] - geom.GetPoint(i)[0]) * j / num_points
                        interp_y = geom.GetPoint(i)[1] + (geom.GetPoint(i+1)[1] - geom.GetPoint(i)[1]) * j / num_points
                        interp_line = ''.join([str(interp_x), ' ', str(interp_y), ' ', '0\n'])
                        print('interp_line', interp_line)
                        interp_line_count += 1
                        fopen.write(line)

    print('Number of lines:', line_count)
    print('Number of interpolated points:', interp_line_count)

    fopen.close()

def poly2xyz(shpin, xyz):
    '''
    reformat polygon-type .shp to .xyz
    :param shpin:
    :param xyz:
    :return:
    '''
    shp_ds = ogr.Open(shpin)
    shp_lyr = shp_ds.GetLayer()

    print ('found %d number of features!' % len(shp_lyr))

    first_line = True

    fopen = open(xyz, 'a')

    for feat in shp_lyr:
        geom = feat.GetGeometryRef()
        ring = geom.GetGeometryRef(0)
        for i in range(0, ring.GetPointCount()):
            if first_line:
                line = ''.join([str(ring.GetPoint(i)[0]), ' ', str(ring.GetPoint(i)[1]), ' ', '1\n'])
                first_line = False
            else:
                line = ''.join([str(ring.GetPoint(i)[0]), ' ', str(ring.GetPoint(i)[1]), ' ', '0\n'])
            fopen.write(line)
    fopen.close()


app = Flask(__name__)

@app.route('/convert-geojson', methods=['POST'])
def convert_shp():
    # 1. 接收前端发送的文件路径
    data = request.json
    shp_path = data.get('shp_path')

    # 确保文件路径不为空且文件存在
    if not shp_path or not os.path.exists(shp_path):
        return jsonify({'error': 'Invalid file path'}), 400

    # 2. 转换SHP文件为GeoJSON
    try:
        gdf = gpd.read_file(shp_path)
        # GeoDataFrame转换为GeoJSON
        geojson = json.loads(gdf.to_json())

        # 3. 保存GeoJSON文件到相同目录
        geojson_path = os.path.splitext(shp_path)[0] + '.geojson'
        with open(geojson_path, 'w') as f:
            json.dump(geojson, f)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # 4. 返回成功消息
    return jsonify({'message': 'shp2geojson-success'})


@app.route('/convert-xyz', methods=['POST'])
def convert_xyz():
    # 接收前端发送的文件路径
    data = request.json
    shp_path = data.get('shp_path')

    # 确保文件路径不为空且文件存在
    if not shp_path or not os.path.exists(shp_path):
        return jsonify({'error': 'Invalid SHP file path'}), 400

    # 根据SHP文件生成TXT文件的路径
    txt_path = os.path.splitext(shp_path)[0] + '.txt'

    # 调用 shp2xyz 函数进行转换
    try:
        shp2xyz(shp_path, txt_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # 返回成功消息
    return jsonify({'message': 'shp2xyz-success'})



if __name__ == '__main__':
    app.run(debug=True)
